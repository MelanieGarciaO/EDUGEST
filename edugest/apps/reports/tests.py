"""Reportes descargables por rol (PDF y Excel)."""

from io import BytesIO

from django.urls import reverse
from openpyxl import load_workbook
from pdfminer.high_level import extract_text

from apps.reinforcement.tests import RefuerzoBase


class ReportesBase(RefuerzoBase):
    def setUp(self):
        super().setUp()
        # est1 (A, rep1): dificultad ALTA en Fracciones y plan aprobado en Matemática.
        # est3 (A, rep2): buena nota en Matemática y dificultad en Lengua.
        # est2 (B, rep2): dificultad en Decimales (Matemática, doc3).
        self.dar_nota(self.est1, self.fracciones, "3.5")
        self.dar_nota(self.est3, self.fracciones, "9.5")
        self.dar_nota(self.est3, self.comprension, "5.0")
        self.dar_nota(self.est2, self.decimales, "6.0", asignacion=self.asig3)
        self.plan = self.generar().data
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))

    def bajar(self, clave, user, **params):
        self.auth(user)
        return self.client.get(reverse("reportes-descargar", args=[clave]), params)

    @staticmethod
    def texto_pdf(res):
        return extract_text(BytesIO(res.content))

    @staticmethod
    def hojas(res):
        wb = load_workbook(BytesIO(res.content))
        return {ws.title: [[c for c in fila] for fila in ws.iter_rows(values_only=True)] for ws in wb}


class CatalogoTests(ReportesBase):
    def catalogo(self, user):
        self.auth(user)
        res = self.client.get(reverse("reportes-catalogo"))
        self.assertEqual(res.status_code, 200)
        return res.data

    def test_reportes_por_rol(self):
        claves = lambda u: [r["clave"] for r in self.catalogo(u)["reportes"]]  # noqa: E731
        self.assertEqual(claves(self.admin), ["resumen", "calificaciones", "dificultades", "planes", "avance"])
        self.assertEqual(claves(self.doc1), ["calificaciones", "dificultades", "planes", "avance"])
        self.assertEqual(claves(self.rep1), ["avance"])

    def test_formatos_y_opciones_visibles(self):
        rep = self.catalogo(self.rep1)
        self.assertEqual(rep["reportes"][0]["formatos"], ["pdf"])
        self.assertEqual([e["id"] for e in rep["opciones"]["estudiante"]], [self.est1.id])
        self.assertNotIn("paralelo", rep["opciones"])

        doc = self.catalogo(self.doc3)
        self.assertEqual(doc["reportes"][0]["formatos"], ["pdf", "xlsx"])
        self.assertEqual([p["id"] for p in doc["opciones"]["paralelo"]], [self.par_b.id])
        self.assertEqual([e["id"] for e in doc["opciones"]["estudiante"]], [self.est2.id])

    def test_requiere_sesion(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("reportes-catalogo")).status_code, 401)


class PermisosTests(ReportesBase):
    def test_representante_solo_avance_en_pdf(self):
        self.assertEqual(self.bajar("calificaciones", self.rep1).status_code, 403)
        self.assertEqual(self.bajar("avance", self.rep1, estudiante=self.est1.id, formato="xlsx").status_code, 400)
        self.assertEqual(self.bajar("avance", self.rep1, estudiante=self.est1.id).status_code, 200)

    def test_no_puede_ver_estudiantes_ajenos(self):
        self.assertEqual(self.bajar("avance", self.rep1, estudiante=self.est2.id).status_code, 404)
        self.assertEqual(self.bajar("avance", self.doc3, estudiante=self.est1.id).status_code, 404)

    def test_resumen_solo_admin(self):
        self.assertEqual(self.bajar("resumen", self.doc1).status_code, 403)
        self.assertEqual(self.bajar("resumen", self.admin).status_code, 200)

    def test_validaciones(self):
        self.assertEqual(self.bajar("avance", self.doc1).status_code, 400)  # estudiante obligatorio
        self.assertEqual(self.bajar("noexiste", self.doc1).status_code, 404)
        self.assertEqual(self.bajar("calificaciones", self.doc1, paralelo=self.par_b.id).status_code, 400)
        self.assertEqual(self.bajar("calificaciones", self.doc1, desde="2026-12-01", hasta="2026-01-01").status_code, 400)
        self.assertEqual(self.bajar("calificaciones", self.doc1, desde="01/12/2026").status_code, 400)
        self.assertEqual(self.bajar("planes", self.doc1, estado_plan="X").status_code, 400)
        self.assertEqual(self.bajar("calificaciones", self.doc1, formato="docx").status_code, 400)


class ContenidoTests(ReportesBase):
    def test_pdf_calificaciones_del_docente(self):
        res = self.bajar("calificaciones", self.doc1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertIn("attachment; filename=\"edugest_calificaciones_", res["Content-Disposition"])
        texto = self.texto_pdf(res)
        self.assertIn("Pérez", texto)
        self.assertIn("Vera", texto)
        self.assertNotIn("Mora", texto)  # est2 es de doc3
        self.assertIn("Página 1 de", texto)

    def test_excel_calificaciones_numeros_reales(self):
        res = self.bajar("calificaciones", self.doc1, formato="xlsx")
        self.assertEqual(res.status_code, 200)
        hojas = self.hojas(res)
        self.assertEqual(list(hojas), ["Promedio por estudiante", "Detalle de notas"])
        filas = hojas["Promedio por estudiante"][6:]
        self.assertIn(["Luis Pérez", "Séptimo EGB A", "Matemática", 1, 3.5, "No alcanza los aprendizajes"], filas)

    def test_dificultades_filtradas(self):
        hojas = self.hojas(self.bajar("dificultades", self.admin, formato="xlsx", asignatura=self.mate.id))
        nombres = [f[0] for f in hojas["Dificultades por tema"][6:]]
        self.assertEqual(sorted(nombres), ["Luis Pérez", "Sofía Mora"])

    def test_planes_y_resultado_por_tema(self):
        hojas = self.hojas(self.bajar("planes", self.doc1, formato="xlsx", estado_plan="APROBADA"))
        plan = hojas["Planes"][6]
        self.assertEqual(plan[:6], ["Luis Pérez", "Séptimo EGB A", "Matemática", self.doc1.full_name, "Alto", "Aprobada"])
        self.assertEqual(plan[6], "0/5")  # 4 del banco + la guía de Reflexión (ERCA)
        self.assertEqual(hojas["Resultado por tema"][6][2], "Fracciones")
        dua = hojas["Apoyos DUA por tema"][6]
        self.assertEqual(dua[2], "Fracciones")
        self.assertIn("material concreto", dua[4])
        self.assertEqual(dua[6], "Reglas del sistema")

    def test_avance_del_representante(self):
        texto = self.texto_pdf(self.bajar("avance", self.rep1, estudiante=self.est1.id))
        for esperado in ("Avance del estudiante", "Luis Pérez", "Fracciones", "Básica 1", "Actividades de refuerzo pendientes"):
            self.assertIn(esperado, texto)

    def test_resumen_institucional(self):
        hojas = self.hojas(self.bajar("resumen", self.admin, formato="xlsx"))
        self.assertEqual(list(hojas), ["Totales", "Por paralelo y asignatura", "Temas con más dificultades"])
        totales = {f[0]: f[1] for f in hojas["Totales"][6:]}
        self.assertEqual(totales["Estudiantes activos"], 3)
        self.assertEqual(totales["Notas registradas"], 4)
        self.assertEqual(totales["Estudiantes con al menos una dificultad"], 3)
        self.assertEqual(totales["Planes vigentes (propuestos o aprobados)"], 1)

    def test_sin_datos_muestra_mensaje(self):
        hojas = self.hojas(self.bajar("planes", self.doc3, formato="xlsx"))
        self.assertEqual(hojas["Planes"][6][0], "Sin datos para los filtros seleccionados.")