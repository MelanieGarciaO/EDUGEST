"""Ciclo ERCA por actividad y apoyos DUA por tema en los planes de refuerzo."""

import json
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from . import dua, erca, ia
from .models import ActividadRefuerzo, FaseErca, RecursoRefuerzo, TemaPlan
from .tests import RefuerzoBase

E, R, C, A = FaseErca.EXPERIENCIA, FaseErca.REFLEXION, FaseErca.CONCEPTUALIZACION, FaseErca.APLICACION


class ErcaReglasTests(RefuerzoBase):
    def fases(self, tema_plan):
        return [(a["titulo"], a["fase"], a["origen"]) for a in tema_plan["actividades"]]

    def test_dificultad_alta_recorre_el_ciclo_en_orden(self):
        tema = self.plan_con({self.fracciones: "3.5"})["temas"][0]
        self.assertEqual(self.fases(tema), [
            ("Básica 1", E, "BANCO"),
            ("¿Qué sé y qué me cuesta de «Fracciones»?", R, "ERCA"),
            ("Básica 2", C, "BANCO"),
            ("Intermedia 1", A, "BANCO"),
            ("Intermedia 2", A, "BANCO"),
        ])
        self.assertEqual([a["orden"] for a in tema["actividades"]], [1, 2, 3, 4, 5])

    def test_moderada_usa_la_primera_intermedia_como_conceptualizacion(self):
        RecursoRefuerzo.objects.create(tema=self.decimales, nivel="INTERMEDIO", titulo="Decimal intermedia 2",
                                       instrucciones="x", creado_por=self.doc1)
        tema = self.plan_con({self.decimales: "6.0"})["temas"][0]
        self.assertEqual([a["fase"] for a in tema["actividades"]], [E, R, C, A])

    def test_respeta_la_fase_del_banco(self):
        RecursoRefuerzo.objects.filter(titulo="Básica 1").update(fase=R)
        tema = self.plan_con({self.fracciones: "3.5"})["temas"][0]
        b1 = next(a for a in tema["actividades"] if a["titulo"] == "Básica 1")
        self.assertEqual(b1["fase"], R)
        self.assertFalse(any(a["origen"] == "ERCA" and a["fase"] == R for a in tema["actividades"]))
        self.assertEqual({a["fase"] for a in tema["actividades"]}, {E, R, C, A})

    def test_toda_actividad_del_plan_tiene_fase(self):
        self.plan_con({self.fracciones: "3.5", self.decimales: "6.0"})
        self.assertFalse(ActividadRefuerzo.objects.filter(fase="").exists())

    def test_funciones_puras(self):
        b = RecursoRefuerzo(nivel="BASICO")
        i = RecursoRefuerzo(nivel="INTERMEDIO")
        self.assertEqual([f for _, f in erca.asignar_fases([b, i])], [E, A])
        self.assertEqual(erca.fases_faltantes([E, A]), [R, C])
        self.assertEqual(erca.fase_por_nivel("BASICO"), C)


class ErcaEdicionTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.tema_id = self.plan["temas"][0]["id"]
        self.act_id = self.plan["temas"][0]["actividades"][0]["id"]
        self.auth(self.doc1)

    def test_el_docente_cambia_la_fase(self):
        res = self.client.patch(reverse("actividad-refuerzo-detail", args=[self.act_id]), {"fase": R}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["fase"], R)
        res = self.client.patch(reverse("actividad-refuerzo-detail", args=[self.act_id]), {"fase": "OTRA"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_agregar_con_fase(self):
        url = reverse("tema-plan-agregar-actividad", args=[self.tema_id])
        res = self.post(url, {"titulo": "Juego", "instrucciones": "Jugar a repartir", "fase": E})
        self.assertEqual(res.data["fase"], E)
        b3 = RecursoRefuerzo.objects.get(titulo="Básica 3")
        self.assertEqual(self.post(url, {"recurso": b3.id}).data["fase"], C)  # básica sin fase -> regla

    def test_aprobado_ya_no_se_cambia(self):
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        res = self.client.patch(reverse("actividad-refuerzo-detail", args=[self.act_id]), {"fase": R}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_banco_acepta_fase(self):
        res = self.post(reverse("recurso-list"), {"tema": self.fracciones.id, "nivel": "BASICO", "titulo": "Pizza",
                                                 "instrucciones": "Repartir la pizza", "fase": E})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["fase"], E)


class DuaTests(RefuerzoBase):
    def test_se_prellena_segun_asignatura_y_nivel(self):
        tema = self.plan_con({self.fracciones: "3.5"})["temas"][0]
        self.assertIn("material concreto", tema["dua_representacion"])
        self.assertIn("sesiones breves", tema["dua_implicacion"])  # dificultad ALTA
        self.assertIn("retirarlos poco a poco", tema["dua_accion_expresion"])
        self.assertEqual(tema["dua_origen"], "REGLAS")

    def test_reglas(self):
        lengua = dua.sugerir("Lengua y Literatura", "Comprensión lectora", "MODERADA")
        self.assertIn("organizadores gráficos", lengua["representacion"])
        self.assertNotIn("sesiones breves", lengua["implicacion"])
        reincidente = dua.sugerir("Ciencias Naturales", "Ecosistemas", "ALTA", reincidente=True)
        self.assertIn("qué le funcionó antes", reincidente["implicacion"])
        manual = dua.sugerir("Matemática", "Fracciones", "MANUAL", motivo="comparar fracciones.")
        self.assertIn("Centrar la evidencia en: comparar fracciones.", manual["accion_expresion"])
        self.assertIn("situaciones de su vida diaria", dua.sugerir("Educación Física", "Saltos", "MODERADA")["implicacion"])

    def test_el_docente_edita_y_queda_como_suyo(self):
        tema_id = self.plan_con({self.fracciones: "3.5"})["temas"][0]["id"]
        self.auth(self.doc1)
        url = reverse("tema-plan-detail", args=[tema_id])
        res = self.client.patch(url, {"dua_implicacion": "  Usar  la tienda   del barrio.  "}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["dua_implicacion"], res.data["dua_origen"]), ("Usar la tienda del barrio.", "DOCENTE"))
        res = self.client.patch(url, {"dua_representacion": "Videos cortos y regletas.", "dua_origen": "IA"}, format="json")
        self.assertEqual(res.data["dua_origen"], "IA")
        self.assertEqual(self.client.patch(url, {"dua_implicacion": "corto"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"dua_implicacion": "x" * 801}, format="json").status_code, 400)
        # Editar solo el objetivo no cambia el origen del DUA.
        res = self.client.patch(url, {"objetivo": "Nuevo objetivo del tema."}, format="json")
        self.assertEqual(res.data["dua_origen"], "IA")

    def test_el_representante_lo_ve_y_no_lo_edita(self):
        plan = self.plan_con({self.fracciones: "3.5"})
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[plan["id"]]))
        self.auth(self.rep1)
        tema = self.client.get(reverse("plan-detail", args=[plan["id"]])).data["temas"][0]
        self.assertTrue(tema["dua_implicacion"])
        res = self.client.patch(reverse("tema-plan-detail", args=[tema["id"]]), {"dua_implicacion": "Hola mundo, prueba."}, format="json")
        self.assertEqual(res.status_code, 403)


@override_settings(GEMINI_API_KEY="clave-de-prueba")
class DuaIATests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.tema = TemaPlan.objects.get(pk=self.plan["temas"][0]["id"])
        self.url = reverse("tema-plan-sugerir-dua", args=[self.tema.id])
        self.auth(self.doc1)
        respuesta = json.dumps({
            "implicacion": "Relacionar las fracciones con repartir una pizza en familia y celebrar cada logro.",
            "representacion": "Usar tiras de papel de colores y ejemplos resueltos paso a paso. Ver https://x.com",
            "accion_expresion": "Que explique en voz alta cómo repartió y dibuje las partes en su cuaderno.",
        })
        parche = mock.patch.object(ia, "_llamar_modelo", return_value=(respuesta, "modelo-a"))
        self.modelo = parche.start()
        self.addCleanup(parche.stop)

    def test_sugiere_sin_guardar_y_sin_datos_del_estudiante(self):
        res = self.post(self.url)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("pizza", res.data["dua"]["implicacion"])
        self.assertNotIn("https://", res.data["dua"]["representacion"])
        self.assertEqual(res.data["modelo"], "modelo-a")
        prompt = self.modelo.call_args.args[1]
        for esperado in ("Matemática", "Fracciones", "Nivel de la dificultad: alta", "[Experiencia] Básica 1"):
            self.assertIn(esperado, prompt)
        for privado in ("Luis", "Pérez", "3.5", "3,50"):
            self.assertNotIn(privado, prompt.split("Objetivo")[0])  # el nombre y la nota no van al modelo
        self.tema.refresh_from_db()
        self.assertEqual(self.tema.dua_origen, "REGLAS")  # no se guardó

    def test_solo_en_propuesta_y_solo_docente(self):
        self.auth(self.rep1)
        self.assertEqual(self.post(self.url).status_code, 403)
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        self.assertEqual(self.post(self.url).status_code, 400)

    def test_respuesta_incompleta(self):
        self.modelo.return_value = (json.dumps({"implicacion": "corto", "representacion": "", "accion_expresion": ""}), "m")
        with self.assertLogs("django.request", level="ERROR"):
            self.assertEqual(self.post(self.url).status_code, 502)

    @override_settings(GEMINI_API_KEY="")
    def test_sin_ia_configurada(self):
        with self.assertLogs("django.request", level="ERROR"):
            self.assertEqual(self.post(self.url).status_code, 503)

    def test_las_propuestas_del_banco_traen_fase(self):
        respuesta = json.dumps({"recursos": [{"titulo": "Pizza de fracciones", "instrucciones": "1. Dibuja una pizza. 2. Repártela. 3. Escribe la fracción.",
                                              "estrategia": "INDIVIDUAL", "duracion_minutos": 20, "fase": "EXPERIENCIA"}]})
        self.modelo.return_value = (respuesta, "modelo-a")
        res = self.post(reverse("recurso-generar-ia"), {"tema": self.fracciones.id, "nivel": "BASICO", "cantidad": 1})
        self.assertEqual(res.data["propuestas"][0]["fase"], "EXPERIENCIA")
        self.assertIn("fase", ia.esquema("")["properties"]["recursos"]["items"]["required"])


class MigracionDatosTests(RefuerzoBase):
    """La migración 0008 completa fases y DUA de planes creados antes de esta mejora."""

    def test_completa_planes_existentes(self):
        import importlib

        tema = self.plan_con({self.fracciones: "3.5"})["temas"][0]
        ActividadRefuerzo.objects.filter(origen="ERCA").delete()  # como un plan antiguo
        ActividadRefuerzo.objects.update(fase="")
        TemaPlan.objects.update(dua_implicacion="", dua_representacion="", dua_accion_expresion="")

        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        # Modelos históricos (sin propiedades), igual que en un «migrate» real.
        estado = MigrationLoader(connection).project_state(("reinforcement", "0008_completar_erca_y_dua"))
        migracion = importlib.import_module("apps.reinforcement.migrations.0008_completar_erca_y_dua")
        migracion.completar(estado.apps, None)

        fases = list(ActividadRefuerzo.objects.order_by("orden").values_list("fase", flat=True))
        self.assertEqual(fases, [E, C, A, A])  # 2 básicas + 2 intermedias, sin agregar guías
        tp = TemaPlan.objects.get(pk=tema["id"])
        self.assertIn("material concreto", tp.dua_representacion)
