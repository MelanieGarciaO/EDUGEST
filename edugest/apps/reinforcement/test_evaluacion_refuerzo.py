"""Evaluación de refuerzo: cierre del ciclo después de completar un plan."""

from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.activities.models import Actividad
from apps.grades import services as grades_services
from apps.grades.models import Dificultad

from . import services
from .models import ActividadRefuerzo, PlanRefuerzo
from .signals import plan_evaluado
from .tests import HOY, RefuerzoBase


class EvaluacionRefuerzoTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self._conectar(plan_evaluado, "evaluado")
        self.plan = self.plan_con({self.fracciones: 6})  # dificultad moderada, promedio 6,00

    # --- utilidades --------------------------------------------------------
    def completar(self):
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        for act in ActividadRefuerzo.objects.filter(tema_plan__plan_id=self.plan["id"]):
            self.auth(self.rep1)
            res = self.post(reverse("actividad-refuerzo-cumplir", args=[act.id]))
            self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(PlanRefuerzo.objects.get(pk=self.plan["id"]).estado, "COMPLETADA")

    def evaluacion(self, valor, tema=None, es_evaluacion=True, estudiante=None, actividad=None):
        actividad = actividad or Actividad.objects.create(
            asignacion=self.asig1, creada_por=self.doc1, descripcion="Evaluación de fracciones",
            fecha_entrega=HOY, es_evaluacion_refuerzo=es_evaluacion,
        )
        with self.captureOnCommitCallbacks(execute=True):
            grades_services.guardar_calificaciones(
                actividad, tema or self.fracciones,
                [((estudiante or self.est1).id, Decimal(str(valor)))], self.doc1,
            )
        return actividad

    def detalle(self, user=None):
        self.auth(user or self.doc1)
        return self.client.get(reverse("plan-detail", args=[self.plan["id"]])).data

    # --- pruebas -----------------------------------------------------------
    def test_plan_completado_queda_pendiente_de_evaluacion(self):
        self.completar()
        plan = self.detalle()
        self.assertEqual(plan["evaluacion"]["estado"], "PENDIENTE")
        self.assertIsNone(plan["temas"][0]["superado"])

    def test_plan_en_curso_no_tiene_evaluacion(self):
        self.assertIsNone(self.detalle()["evaluacion"])

    def test_evaluacion_que_alcanza_7_supera_el_tema_y_la_dificultad(self):
        self.completar()
        self.evaluacion(8)  # (6 + 8) / 2 = 7,00
        plan = self.detalle()
        tema = plan["temas"][0]
        self.assertEqual((tema["superado"], tema["nota_evaluacion"], tema["promedio_final"]), (True, "8.00", "7.00"))
        self.assertEqual(plan["evaluacion"]["estado"], "EVALUADO")
        self.assertEqual(plan["evaluacion"]["resultado"], "SUPERADO")
        self.assertEqual(Dificultad.objects.get(estudiante=self.est1, tema=self.fracciones).estado, "SUPERADA")
        self.assertIn(("evaluado", self.plan["id"]), self.eventos)

    def test_evaluacion_insuficiente_permite_generar_un_nuevo_plan(self):
        self.completar()
        self.evaluacion(6.5)  # nota de la evaluación < 7
        plan = self.detalle()
        self.assertFalse(plan["temas"][0]["superado"])
        self.assertEqual(plan["evaluacion"]["resultado"], "NO_SUPERADO")
        self.assertEqual(self.generar().status_code, 201)

    def test_el_representante_ve_el_resultado(self):
        self.completar()
        self.evaluacion(9)
        plan = self.detalle(self.rep1)
        self.assertEqual(plan["evaluacion"]["resultado"], "SUPERADO")

    def test_una_actividad_normal_no_cuenta_como_evaluacion(self):
        self.completar()
        self.evaluacion(9, es_evaluacion=False)
        plan = self.detalle()
        self.assertEqual(plan["evaluacion"]["estado"], "PENDIENTE")
        # La dificultad sí se recalcula con la nota normal.
        self.assertEqual(Dificultad.objects.get(estudiante=self.est1, tema=self.fracciones).estado, "SUPERADA")

    def test_evaluacion_antes_de_completar_el_plan_no_cuenta(self):
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        actividad = self.evaluacion(9)
        PlanRefuerzo.objects.filter(pk=self.plan["id"]).update(estado="COMPLETADA", completado_en=timezone.now() + timedelta(seconds=1))
        services.sincronizar_evaluaciones(actividad, [self.est1.id])  # la nota es anterior
        self.assertEqual(self.detalle()["evaluacion"]["estado"], "PENDIENTE")

    def test_corregir_la_nota_actualiza_el_resultado(self):
        self.completar()
        actividad = self.evaluacion(6.5)
        self.assertFalse(self.detalle()["temas"][0]["superado"])
        self.evaluacion(9, actividad=actividad)  # corrección
        tema = self.detalle()["temas"][0]
        self.assertEqual((tema["superado"], tema["nota_evaluacion"], tema["promedio_final"]), (True, "9.00", "7.50"))
        # Y al revés: bajar una evaluación aprobada vuelve a abrir el tema y la dificultad.
        self.evaluacion(5, actividad=actividad)
        self.assertFalse(self.detalle()["temas"][0]["superado"])
        self.assertEqual(self.dificultad().estado, "DETECTADA")

    # --- regla: se supera con la nota de la evaluación, no con el promedio histórico ---
    def dificultad(self):
        return Dificultad.objects.get(estudiante=self.est1, tema=self.fracciones)

    def test_historial_bajo_no_impide_superar_con_una_buena_evaluacion(self):
        self.completar()
        self.evaluacion(3, es_evaluacion=False)  # otra nota baja: historial 6 y 3
        self.evaluacion(8)  # promedio histórico (6 + 3 + 8) / 3 = 5,67
        tema = self.detalle()["temas"][0]
        self.assertEqual((tema["superado"], tema["nota_evaluacion"], tema["promedio_final"]), (True, "8.00", "5.67"))
        self.assertEqual(self.dificultad().estado, "SUPERADA")
        self.assertEqual(self.detalle()["evaluacion"]["resultado"], "SUPERADO")

    def test_evaluacion_de_7_exacto_supera(self):
        self.completar()
        self.evaluacion(7)
        self.assertTrue(self.detalle()["temas"][0]["superado"])

    def test_evaluacion_reprobada_no_reinicia_el_promedio(self):
        self.completar()
        self.evaluacion(6.9)
        dificultad = self.dificultad()
        self.assertEqual((dificultad.estado, dificultad.promedio), ("DETECTADA", Decimal("6.45")))

    def test_notas_despues_de_superar_cuentan_desde_la_evaluacion(self):
        self.completar()
        self.evaluacion(8)
        self.evaluacion(9, es_evaluacion=False)  # desde el corte: (8 + 9) / 2 = 8,50
        self.assertEqual((self.dificultad().estado, self.dificultad().promedio), ("SUPERADA", Decimal("8.50")))
        self.evaluacion(2, es_evaluacion=False)  # (8 + 9 + 2) / 3 = 6,33 -> reincide
        dificultad = self.dificultad()
        self.assertEqual((dificultad.estado, dificultad.veces_detectada), ("DETECTADA", 2))
        self.assertEqual(dificultad.promedio, Decimal("6.33"))

    def test_nota_en_un_subtema_evalua_el_tema_del_plan(self):
        self.completar()
        self.evaluacion(8, tema=self.equivalentes)
        self.assertIsNotNone(self.detalle()["temas"][0]["superado"])

    def test_reabrir_una_actividad_anula_la_evaluacion(self):
        self.completar()
        self.evaluacion(9)
        act = ActividadRefuerzo.objects.filter(tema_plan__plan_id=self.plan["id"]).first()
        self.auth(self.doc1)
        self.post(reverse("actividad-refuerzo-reabrir", args=[act.id]))
        plan = self.detalle()
        self.assertEqual(plan["estado"], "APROBADA")
        self.assertIsNone(plan["temas"][0]["superado"])

    def test_filtro_de_planes_pendientes_de_evaluacion(self):
        self.completar()
        self.auth(self.doc1)
        url = reverse("plan-list")
        self.assertEqual(self.client.get(url, {"evaluacion": "pendiente"}).data["count"], 1)
        self.evaluacion(9)
        self.assertEqual(self.client.get(url, {"evaluacion": "pendiente"}).data["count"], 0)
        self.assertEqual(self.client.get(url, {"evaluacion": "evaluado"}).data["count"], 1)
        self.assertEqual(self.client.get(url, {"evaluacion": "otro"}).status_code, 400)

    def test_dificultad_muestra_el_estado_del_refuerzo(self):
        url = reverse("dificultad-list")
        self.auth(self.doc1)
        self.assertEqual(self.client.get(url).data["results"][0]["refuerzo"], "EN_CURSO")
        self.completar()
        self.auth(self.doc1)
        self.assertEqual(self.client.get(url).data["results"][0]["refuerzo"], "PENDIENTE_EVALUACION")

    def test_otros_estudiantes_de_la_evaluacion_no_se_ven_afectados(self):
        self.completar()
        actividad = self.evaluacion(9)
        self.evaluacion(3, estudiante=self.est3, actividad=actividad)
        self.assertTrue(self.detalle()["temas"][0]["superado"])

    def test_docente_publica_una_evaluacion_de_refuerzo(self):
        self.auth(self.doc1)
        res = self.post(reverse("actividad-list"), {
            "paralelo": self.par_a.id, "asignatura": self.mate.id,
            "descripcion": "Evaluación de fracciones",
            "fecha_entrega": str(timezone.localdate() + timedelta(days=2)),
            "es_evaluacion_refuerzo": True,
        })
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["es_evaluacion_refuerzo"])
