from datetime import date, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.academic.models import (
    Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo, Tema,
)
from apps.activities.models import Actividad
from apps.security.models import Role, User
from apps.security.serializers import LoginSerializer

from .models import Calificacion, CalificacionHistorial, Dificultad
from .signals import dificultad_detectada, dificultad_superada

PASSWORD = "ClaveSegura2026"
HOY = date(2026, 10, 1)
MANANA = HOY + timedelta(days=1)


def make_user(email, role, **extra):
    extra.setdefault("must_change_password", False)
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Nombre", last_name=email.split("@")[0],
        role=role, **extra,
    )


class GradesBase(APITestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("django.utils.timezone.localdate", return_value=HOY)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.admin = make_user("admin@edugest.test", Role.ADMINISTRADOR)
        self.doc1 = make_user("doc1@edugest.test", Role.DOCENTE)
        self.doc2 = make_user("doc2@edugest.test", Role.DOCENTE)
        self.rep1 = make_user("rep1@edugest.test", Role.REPRESENTANTE)
        self.rep2 = make_user("rep2@edugest.test", Role.REPRESENTANTE)

        self.grado7 = Grado.objects.create(nombre="Séptimo EGB", orden=7)
        self.grado8 = Grado.objects.create(nombre="Octavo EGB", orden=8)
        self.par_a = Paralelo.objects.create(grado=self.grado7, nombre="A")
        self.par_b = Paralelo.objects.create(grado=self.grado7, nombre="B")
        self.mate = Asignatura.objects.create(nombre="Matemática")
        self.lengua = Asignatura.objects.create(nombre="Lengua y Literatura")

        # doc1: Matemática en A. doc2: Lengua en B y Lengua en A.
        self.asig1 = AsignacionDocente.objects.create(docente=self.doc1, paralelo=self.par_a, asignatura=self.mate)
        self.asig2 = AsignacionDocente.objects.create(docente=self.doc2, paralelo=self.par_b, asignatura=self.lengua)
        self.asig3 = AsignacionDocente.objects.create(docente=self.doc2, paralelo=self.par_a, asignatura=self.lengua)

        self.est1 = Estudiante.objects.create(first_name="Luis", last_name="Pérez", paralelo=self.par_a, representante=self.rep1)
        self.est3 = Estudiante.objects.create(first_name="Marta", last_name="Vera", paralelo=self.par_a, representante=self.rep2)
        self.est2 = Estudiante.objects.create(first_name="Sofía", last_name="Mora", paralelo=self.par_b, representante=self.rep2)

        self.fracciones = Tema.objects.create(grado=self.grado7, asignatura=self.mate, nombre="Fracciones")
        self.equivalentes = Tema.objects.create(
            grado=self.grado7, asignatura=self.mate, padre=self.fracciones, nombre="Fracciones equivalentes"
        )
        self.decimales = Tema.objects.create(grado=self.grado7, asignatura=self.mate, nombre="Decimales")
        self.comprension = Tema.objects.create(grado=self.grado7, asignatura=self.lengua, nombre="Comprensión lectora")

        self.act1 = self.actividad(self.asig1, "Páginas 20 y 21")
        self.act2 = self.actividad(self.asig1, "Páginas 22 y 23")
        self.act_lengua_a = self.actividad(self.asig3, "Leer el capítulo 3")
        self.act_lengua_b = self.actividad(self.asig2, "Resumen del texto")

        self.eventos = []
        self._conectar(dificultad_detectada, "detectada")
        self._conectar(dificultad_superada, "superada")

    def actividad(self, asignacion, descripcion, fecha=HOY, **extra):
        return Actividad.objects.create(
            asignacion=asignacion, creada_por=asignacion.docente,
            descripcion=descripcion, fecha_entrega=fecha, **extra,
        )

    def _conectar(self, senal, nombre):
        def receptor(sender, dificultad, **kwargs):
            self.eventos.append((nombre, dificultad.estudiante_id, dificultad.tema_id))

        senal.connect(receptor, weak=False)
        self.addCleanup(senal.disconnect, receptor)

    def auth(self, user):
        token = LoginSerializer.get_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def url_notas(self, actividad):
        return reverse("actividad-calificaciones", args=[actividad.id])

    def guardar(self, user, actividad, tema, notas):
        """Guarda notas {estudiante: valor} y ejecuta los eventos al confirmar."""
        self.auth(user)
        cuerpo = {
            "tema": tema.id,
            "calificaciones": [{"estudiante": e.id, "valor": str(v)} for e, v in notas.items()],
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url_notas(actividad), cuerpo, format="json")

    @staticmethod
    def ids(response):
        return sorted(item["id"] for item in response.data["results"])


# ---------------------------------------------------------------------------
class GuardarTests(GradesBase):
    def test_guarda_y_devuelve_resumen_con_dificultades(self):
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0", self.est3: "9.5"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["creadas"], res.data["actualizadas"], res.data["sin_cambios"]), (2, 0, 0))

        niveles = {c["estudiante"]: c["nivel"] for c in res.data["calificaciones"]}
        self.assertEqual(niveles[self.est1.id], "PROXIMO")
        self.assertEqual(niveles[self.est3.id], "DOMINA")

        self.assertEqual(len(res.data["dificultades"]), 1)
        dif = res.data["dificultades"][0]
        self.assertEqual(dif["estudiante"], self.est1.id)
        self.assertEqual((dif["nivel"], dif["estado"], dif["promedio"]), ("MODERADA", "DETECTADA", "6.00"))
        self.assertEqual(self.eventos, [("detectada", self.est1.id, self.fracciones.id)])

    def test_dificultad_alta(self):
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "3.5"})
        self.assertEqual(res.data["dificultades"][0]["nivel"], "ALTA")

    def test_nota_de_siete_no_es_dificultad(self):
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "7.00"})
        self.assertEqual(res.data["dificultades"], [])
        self.assertFalse(Dificultad.objects.exists())

    def test_el_promedio_considera_varias_actividades(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0"})
        res = self.guardar(self.doc1, self.act2, self.fracciones, {self.est1: "7.5"})
        # (6.0 + 7.5) / 2 = 6.75: sigue con dificultad moderada.
        dif = res.data["dificultades"][0]
        self.assertEqual((dif["promedio"], dif["num_calificaciones"]), ("6.75", 2))

        res = self.guardar(self.doc1, self.act2, self.fracciones, {self.est1: "9.0"})
        # Se corrige la segunda nota: (6.0 + 9.0) / 2 = 7.50 -> dificultad superada.
        self.assertEqual(res.data["dificultades"], [])
        self.assertEqual(Dificultad.objects.get().estado, "SUPERADA")
        self.assertEqual(
            self.eventos,
            [("detectada", self.est1.id, self.fracciones.id), ("superada", self.est1.id, self.fracciones.id)],
        )

    def test_correccion_deja_historial(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "8.0"})
        self.assertEqual((res.data["creadas"], res.data["actualizadas"]), (0, 1))

        nota = Calificacion.objects.get()
        self.assertEqual(str(nota.valor), "8.00")
        registro = CalificacionHistorial.objects.get()
        self.assertEqual((str(registro.valor_anterior), str(registro.valor_nuevo)), ("5.00", "8.00"))
        self.assertEqual(registro.modificado_por, self.doc1)
        self.assertEqual(nota.registrada_por, self.doc1)

        url = reverse("calificacion-historial", args=[nota.id])
        for user in (self.doc1, self.admin):
            self.auth(user)
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(res.data), 1)
            self.assertEqual(res.data[0]["valor_anterior"], "5.00")
        self.auth(self.rep1)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_reenviar_lo_mismo_no_cambia_nada(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.eventos.clear()
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.00"})
        self.assertEqual((res.data["creadas"], res.data["actualizadas"], res.data["sin_cambios"]), (0, 0, 1))
        self.assertFalse(CalificacionHistorial.objects.exists())
        self.assertEqual(self.eventos, [])

    def test_dificultad_superada_y_reabierta(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "8.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "4.5"})
        dificultad = Dificultad.objects.get()
        self.assertEqual((dificultad.estado, dificultad.nivel), ("DETECTADA", "MODERADA"))
        self.assertIsNone(dificultad.superada_en)
        self.assertEqual([e[0] for e in self.eventos], ["detectada", "superada", "detectada"])

    def test_cambiar_de_tema_recalcula_el_tema_anterior_y_el_nuevo(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act1, self.decimales, {self.est1: "5.0"})
        por_tema = {d.tema_id: d.estado for d in Dificultad.objects.all()}
        self.assertEqual(por_tema, {self.fracciones.id: "SUPERADA", self.decimales.id: "DETECTADA"})
        registro = CalificacionHistorial.objects.get()
        self.assertEqual((registro.tema_anterior, registro.tema_nuevo), (self.fracciones, self.decimales))

    def test_tema_y_subtema_se_evaluan_por_separado(self):
        self.guardar(self.doc1, self.act1, self.equivalentes, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act2, self.fracciones, {self.est1: "9.0"})
        dificultades = {d.tema_id for d in Dificultad.objects.filter(estado="DETECTADA")}
        self.assertEqual(dificultades, {self.equivalentes.id})

    def test_estudiantes_no_incluidos_no_cambian(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0", self.est3: "9.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0"})
        self.assertEqual(str(Calificacion.objects.get(estudiante=self.est3).valor), "9.00")

    @override_settings(GRADES_MIN_CALIFICACIONES=2)
    def test_minimo_de_calificaciones_configurable(self):
        res = self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.assertEqual(res.data["dificultades"], [])
        res = self.guardar(self.doc1, self.act2, self.fracciones, {self.est1: "5.0"})
        self.assertEqual(len(res.data["dificultades"]), 1)


# ---------------------------------------------------------------------------
class ValidacionTests(GradesBase):
    def enviar(self, calificaciones, tema=None, actividad=None):
        self.auth(self.doc1)
        return self.client.post(
            self.url_notas(actividad or self.act1),
            {"tema": (tema or self.fracciones).id, "calificaciones": calificaciones},
            format="json",
        )

    def test_notas_fuera_de_rango_o_mal_formadas(self):
        for valor in ("10.5", "-1", "8.555", "abc", None):
            with self.subTest(valor=valor):
                res = self.enviar([{"estudiante": self.est1.id, "valor": valor}])
                self.assertEqual(res.status_code, 400)
        self.assertFalse(Calificacion.objects.exists())

    def test_limites_validos(self):
        res = self.enviar([{"estudiante": self.est1.id, "valor": "0"}, {"estudiante": self.est3.id, "valor": "10"}])
        self.assertEqual(res.status_code, 200)

    def test_lista_vacia(self):
        self.assertEqual(self.enviar([]).status_code, 400)

    def test_demasiados_estudiantes(self):
        items = [{"estudiante": i, "valor": "8"} for i in range(1, 102)]
        self.assertEqual(self.enviar(items).status_code, 400)

    def test_estudiantes_repetidos(self):
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}, {"estudiante": self.est1.id, "valor": "9"}])
        self.assertEqual(res.status_code, 400)

    def test_estudiante_de_otro_paralelo_inactivo_o_inexistente(self):
        self.assertEqual(self.enviar([{"estudiante": self.est2.id, "valor": "8"}]).status_code, 400)
        self.assertEqual(self.enviar([{"estudiante": 99999, "valor": "8"}]).status_code, 400)
        self.est1.is_active = False
        self.est1.save()
        self.assertEqual(self.enviar([{"estudiante": self.est1.id, "valor": "8"}]).status_code, 400)

    def test_un_envio_con_un_error_no_guarda_nada(self):
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}, {"estudiante": self.est2.id, "valor": "8"}])
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Calificacion.objects.exists())

    def test_tema_de_otra_asignatura_o_grado(self):
        item = [{"estudiante": self.est1.id, "valor": "8"}]
        self.assertEqual(self.enviar(item, tema=self.comprension).status_code, 400)
        otro_grado = Tema.objects.create(grado=self.grado8, asignatura=self.mate, nombre="Álgebra")
        self.assertEqual(self.enviar(item, tema=otro_grado).status_code, 400)

    def test_tema_inactivo(self):
        self.decimales.is_active = False
        self.decimales.save()
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}], tema=self.decimales)
        self.assertEqual(res.status_code, 400)

    def test_actividad_cancelada(self):
        self.act1.estado = Actividad.Estado.CANCELADA
        self.act1.save()
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}])
        self.assertEqual(res.status_code, 400)
        self.assertIn("cancelada", res.data["detail"])

    def test_solo_desde_el_dia_de_entrega(self):
        futura = self.actividad(self.asig1, "Para mañana", fecha=MANANA)
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}], actividad=futura)
        self.assertEqual(res.status_code, 400)
        self.assertIn("día de entrega", res.data["detail"])

    def test_actividad_vencida_si_se_puede_calificar(self):
        vencida = self.actividad(self.asig1, "De la semana pasada", fecha=HOY - timedelta(days=7))
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}], actividad=vencida)
        self.assertEqual(res.status_code, 200)

    def test_asignacion_inactiva(self):
        self.asig1.is_active = False
        self.asig1.save()
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}])
        self.assertEqual(res.status_code, 400)


# ---------------------------------------------------------------------------
class PermisosTests(GradesBase):
    def cuerpo(self):
        return {"tema": self.fracciones.id, "calificaciones": [{"estudiante": self.est1.id, "valor": "8"}]}

    def test_otro_docente_no_encuentra_la_actividad(self):
        self.auth(self.doc2)
        self.assertEqual(self.client.post(self.url_notas(self.act1), self.cuerpo(), format="json").status_code, 404)
        self.assertEqual(self.client.get(self.url_notas(self.act1)).status_code, 404)

    def test_representante_y_admin_no_califican(self):
        for user in (self.rep1, self.admin):
            self.auth(user)
            res = self.client.post(self.url_notas(self.act1), self.cuerpo(), format="json")
            self.assertEqual(res.status_code, 403)

    def test_requiere_autenticacion(self):
        self.assertEqual(self.client.post(self.url_notas(self.act1), self.cuerpo(), format="json").status_code, 401)

    def test_clave_temporal_bloquea(self):
        temporal = make_user("temp@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(temporal)
        self.assertEqual(self.client.post(self.url_notas(self.act1), self.cuerpo(), format="json").status_code, 403)

    def test_vista_de_la_actividad_no_es_para_representantes(self):
        self.auth(self.rep1)
        self.assertEqual(self.client.get(self.url_notas(self.act1)).status_code, 403)


# ---------------------------------------------------------------------------
class VistaDeActividadTests(GradesBase):
    def test_lista_estudiantes_con_y_sin_nota(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0"})
        self.auth(self.doc1)
        res = self.client.get(self.url_notas(self.act1))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["resumen"], {"estudiantes": 2, "calificados": 1, "sin_calificar": 1, "promedio": "6.00"})
        filas = {f["estudiante"]: f for f in res.data["calificaciones"]}
        self.assertEqual(filas[self.est1.id]["valor"], "6.00")
        self.assertEqual(filas[self.est1.id]["tema_nombre"], "Fracciones")
        self.assertIsNone(filas[self.est3.id]["valor"])  # "sin calificar", no es cero
        self.assertNotIn(self.est2.id, filas)  # otro paralelo

    def test_administrador_puede_consultar(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url_notas(self.act1)).status_code, 200)

    def test_estudiante_inactivo_no_aparece(self):
        self.est3.is_active = False
        self.est3.save()
        self.auth(self.doc1)
        res = self.client.get(self.url_notas(self.act1))
        self.assertEqual(res.data["resumen"]["estudiantes"], 1)


# ---------------------------------------------------------------------------
class ConsultaTests(GradesBase):
    url = "/api/grades/calificaciones/"

    def setUp(self):
        super().setUp()
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0", self.est3: "9.0"})
        self.guardar(self.doc2, self.act_lengua_a, self.comprension, {self.est1: "8.0"})
        self.guardar(self.doc2, self.act_lengua_b, self.comprension, {self.est2: "4.0"})
        self.nota = lambda estudiante, actividad: Calificacion.objects.get(
            estudiante=estudiante, actividad=actividad
        ).id

    def test_docente_ve_solo_las_notas_de_sus_actividades(self):
        self.auth(self.doc1)
        res = self.client.get(self.url)
        self.assertEqual(self.ids(res), sorted([self.nota(self.est1, self.act1), self.nota(self.est3, self.act1)]))

    def test_representante_ve_todas_las_asignaturas_de_su_estudiante_y_nada_mas(self):
        self.auth(self.rep1)
        res = self.client.get(self.url)
        self.assertEqual(
            self.ids(res), sorted([self.nota(self.est1, self.act1), self.nota(self.est1, self.act_lengua_a)])
        )
        # No puede abrir la nota de otro estudiante.
        self.assertEqual(
            self.client.get(reverse("calificacion-detail", args=[self.nota(self.est3, self.act1)])).status_code, 404
        )

    def test_representante_con_dos_estudiantes(self):
        self.auth(self.rep2)
        self.assertEqual(self.client.get(self.url).data["count"], 2)  # Marta (mate) y Sofía (lengua)

    def test_administrador_ve_todo(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url).data["count"], 4)

    def test_filtros(self):
        self.auth(self.admin)
        por_est = self.client.get(self.url, {"estudiante": self.est1.id})
        self.assertEqual(por_est.data["count"], 2)
        por_asig = self.client.get(self.url, {"asignatura": self.lengua.id})
        self.assertEqual(por_asig.data["count"], 2)
        por_tema = self.client.get(self.url, {"tema": self.fracciones.id})
        self.assertEqual(por_tema.data["count"], 2)
        por_par = self.client.get(self.url, {"paralelo": self.par_b.id})
        self.assertEqual(por_par.data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"actividad": "x"}).status_code, 400)

    def test_requiere_autenticacion(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)


# ---------------------------------------------------------------------------
class DesempenoTests(GradesBase):
    def setUp(self):
        super().setUp()
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "6.0"})
        self.guardar(self.doc1, self.act2, self.equivalentes, {self.est1: "8.0"})
        self.guardar(self.doc2, self.act_lengua_a, self.comprension, {self.est1: "9.0"})

    def url(self, estudiante):
        return reverse("desempeno-estudiante", args=[estudiante.id])

    @staticmethod
    def por_nombre(items):
        return {i["nombre"]: i for i in items}

    def test_representante_ve_todas_las_asignaturas(self):
        self.auth(self.rep1)
        res = self.client.get(self.url(self.est1))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["estudiante"]["nombre"], "Luis Pérez")
        asignaturas = self.por_nombre(res.data["asignaturas"])
        self.assertEqual(set(asignaturas), {"Matemática", "Lengua y Literatura"})

        mate = asignaturas["Matemática"]
        self.assertEqual((mate["promedio"], mate["nivel"], mate["calificaciones"]), ("7.00", "ALCANZA", 2))
        fracciones = self.por_nombre(mate["temas"])["Fracciones"]
        # El promedio del tema padre incluye al subtema: (6.0 + 8.0) / 2.
        self.assertEqual((fracciones["promedio"], fracciones["calificaciones"]), ("7.00", 2))
        sub = self.por_nombre(fracciones["subtemas"])["Fracciones equivalentes"]
        self.assertEqual((sub["promedio"], sub["nivel"]), ("8.00", "ALCANZA"))
        # Pero la dificultad se evalúa solo con las notas propias del tema (6.0).
        self.assertEqual(
            fracciones["dificultad"],
            {"nivel": "MODERADA", "estado": "DETECTADA", "reincidente": False, "veces_detectada": 1},
        )
        self.assertIsNone(sub["dificultad"])

        lengua = asignaturas["Lengua y Literatura"]
        self.assertEqual((lengua["promedio"], lengua["nivel"]), ("9.00", "DOMINA"))

    def test_el_docente_solo_ve_sus_asignaturas(self):
        self.auth(self.doc1)
        nombres = [a["nombre"] for a in self.client.get(self.url(self.est1)).data["asignaturas"]]
        self.assertEqual(nombres, ["Matemática"])
        self.auth(self.doc2)
        nombres = [a["nombre"] for a in self.client.get(self.url(self.est1)).data["asignaturas"]]
        self.assertEqual(nombres, ["Lengua y Literatura"])

    def test_administrador_ve_todo(self):
        self.auth(self.admin)
        self.assertEqual(len(self.client.get(self.url(self.est1)).data["asignaturas"]), 2)

    def test_estudiantes_ajenos_no_se_encuentran(self):
        self.auth(self.rep1)
        self.assertEqual(self.client.get(self.url(self.est3)).status_code, 404)
        self.auth(self.doc1)
        self.assertEqual(self.client.get(self.url(self.est2)).status_code, 404)  # otro paralelo

    def test_sin_notas(self):
        self.auth(self.rep2)
        res = self.client.get(self.url(self.est3))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["asignaturas"], [])

    def test_requiere_autenticacion(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url(self.est1)).status_code, 401)


# ---------------------------------------------------------------------------
class DificultadesTests(GradesBase):
    url = "/api/grades/dificultades/"

    def setUp(self):
        super().setUp()
        # est1: dificultad en Fracciones (Matemática, doc1) y en Comprensión (Lengua, doc2) en A.
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc2, self.act_lengua_a, self.comprension, {self.est1: "3.0"})
        # est2 (paralelo B): dificultad en Comprensión con doc2.
        self.guardar(self.doc2, self.act_lengua_b, self.comprension, {self.est2: "6.5"})

    def pares(self, res):
        return sorted((d["estudiante"], d["tema"]) for d in res.data["results"])

    def test_docente_ve_solo_los_temas_de_sus_asignaturas_en_sus_paralelos(self):
        self.auth(self.doc1)
        self.assertEqual(self.pares(self.client.get(self.url)), [(self.est1.id, self.fracciones.id)])
        # doc2 comparte el paralelo A, pero no puede ver la dificultad en Matemática.
        self.auth(self.doc2)
        self.assertEqual(
            self.pares(self.client.get(self.url)),
            sorted([(self.est1.id, self.comprension.id), (self.est2.id, self.comprension.id)]),
        )

    def test_representante_ve_las_de_sus_estudiantes(self):
        self.auth(self.rep1)
        self.assertEqual(
            self.pares(self.client.get(self.url)),
            sorted([(self.est1.id, self.fracciones.id), (self.est1.id, self.comprension.id)]),
        )
        self.auth(self.rep2)
        self.assertEqual(self.pares(self.client.get(self.url)), [(self.est2.id, self.comprension.id)])

    def test_administrador_ve_todas(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url).data["count"], 3)

    def test_filtros(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url, {"nivel": "alta"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"nivel": "MODERADA"}).data["count"], 2)
        self.assertEqual(self.client.get(self.url, {"asignatura": self.mate.id}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"paralelo": self.par_b.id}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"estudiante": self.est1.id}).data["count"], 2)
        self.assertEqual(self.client.get(self.url, {"estado": "SUPERADA"}).data["count"], 0)

    def test_filtro_de_estado_tras_superar(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "9.0"})
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url, {"estado": "superada"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"estado": "DETECTADA"}).data["count"], 2)

    def test_valores_de_filtro_invalidos(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url, {"estado": "otra"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"nivel": "otra"}).status_code, 400)

    def test_detalle_ajeno_no_se_encuentra(self):
        dificultad = Dificultad.objects.get(estudiante=self.est1, tema=self.fracciones)
        self.auth(self.rep2)
        self.assertEqual(self.client.get(reverse("dificultad-detail", args=[dificultad.id])).status_code, 404)
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("dificultad-detail", args=[dificultad.id])).status_code, 200)

    def test_requiere_autenticacion(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
