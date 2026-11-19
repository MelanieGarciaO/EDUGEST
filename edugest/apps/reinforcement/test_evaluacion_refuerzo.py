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
        self.completar()  # solo se publica si alguien completó su plan
        self.auth(self.doc1)
        res = self.post(reverse("actividad-list"), {
            "paralelo": self.par_a.id, "asignatura": self.mate.id,
            "descripcion": "Evaluación de fracciones",
            "fecha_entrega": str(timezone.localdate() + timedelta(days=2)),
            "es_evaluacion_refuerzo": True,
        })
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["es_evaluacion_refuerzo"])



class EvaluacionSoloPlanCompletadoTests(RefuerzoBase):
    """La evaluación de refuerzo es solo para quienes completaron su plan al 100 %."""

    def setUp(self):
        super().setUp()
        # Luis (est1, rep1) tiene plan de Matemática; Marta (est3, rep2) está en el mismo paralelo sin plan.
        self.plan = self.plan_con({self.fracciones: 6})

    def completar(self):
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        self.auth(self.rep1)
        for act in ActividadRefuerzo.objects.filter(tema_plan__plan_id=self.plan["id"]):
            self.post(reverse("actividad-refuerzo-cumplir", args=[act.id]))
        self.assertEqual(PlanRefuerzo.objects.get(pk=self.plan["id"]).estado, "COMPLETADA")

    def publicar(self, **extra):
        self.auth(self.doc1)
        datos = {
            "paralelo": self.par_a.id, "asignatura": self.mate.id, "descripcion": "Evaluación de fracciones",
            "fecha_entrega": str(timezone.localdate() + timedelta(days=2)), "es_evaluacion_refuerzo": True,
        }
        datos.update(extra)
        with self.captureOnCommitCallbacks(execute=True):
            return self.post(reverse("actividad-list"), datos)

    def calificar(self, actividad_id, notas, tema=None):
        # Solo se califica desde el día de entrega.
        Actividad.objects.filter(pk=actividad_id).update(fecha_entrega=timezone.localdate())
        self.auth(self.doc1)
        return self.post(reverse("actividad-calificaciones", args=[actividad_id]), {
            "tema": (tema or self.fracciones).id,
            "calificaciones": [{"estudiante": e.id, "valor": str(v)} for e, v in notas],
        })

    def ids_visibles(self, user):
        self.auth(user)
        return [a["id"] for a in self.client.get(reverse("actividad-list")).data["results"]]

    def test_sin_planes_completados_no_se_puede_publicar(self):
        res = self.publicar()  # el plan de Luis aún está en curso
        self.assertEqual(res.status_code, 400)
        self.assertIn("100 %", str(res.data["es_evaluacion_refuerzo"]))
        self.assertEqual(self.publicar(es_evaluacion_refuerzo=False).status_code, 201)  # normal: sí

    def test_va_solo_a_quien_completo_su_plan(self):
        self.completar()
        res = self.publicar()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["destinatarios"], [{"id": self.est1.id, "nombre": self.est1.full_name}])
        actividad = res.data["id"]

        # Familias: solo la de Luis la ve; la de Marta no.
        self.assertIn(actividad, self.ids_visibles(self.rep1))
        self.assertNotIn(actividad, self.ids_visibles(self.rep2))
        self.auth(self.rep2)
        self.assertEqual(self.client.get(reverse("actividad-detail", args=[actividad])).status_code, 404)

        # Calificar: solo aparece Luis.
        self.auth(self.doc1)
        filas = self.client.get(reverse("actividad-calificaciones", args=[actividad])).data
        self.assertEqual([f["estudiante"] for f in filas["calificaciones"]], [self.est1.id])
        self.assertTrue(filas["actividad"]["es_evaluacion_refuerzo"])

    def test_solo_avisa_a_la_familia_del_destinatario(self):
        from apps.notifications.models import Notificacion

        self.completar()
        Notificacion.objects.all().delete()
        self.assertEqual(self.publicar().status_code, 201)
        self.assertTrue(Notificacion.objects.filter(usuario=self.rep1).exists())
        self.assertFalse(Notificacion.objects.filter(usuario=self.rep2).exists())

    def test_no_se_califica_a_quien_no_es_destinatario(self):
        self.completar()
        actividad = self.publicar().data["id"]
        res = self.calificar(actividad, [(self.est3, 9)])
        self.assertEqual(res.status_code, 400)
        self.assertIn("completaron su plan", str(res.data["calificaciones"]))

    def test_el_tema_debe_estar_en_su_plan(self):
        self.completar()
        actividad = self.publicar().data["id"]
        res = self.calificar(actividad, [(self.est1, 9)], tema=self.decimales)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Luis", str(res.data["tema"]))
        # Un subtema del tema reforzado sí vale.
        self.assertEqual(self.calificar(actividad, [(self.est1, 9)], tema=self.equivalentes).status_code, 200)

    def test_la_nota_evalua_el_plan_y_cuenta_en_el_promedio(self):
        self.completar()
        actividad = self.publicar().data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.calificar(actividad, [(self.est1, 8)]).status_code, 200)
        self.auth(self.doc1)
        plan = self.client.get(reverse("plan-detail", args=[self.plan["id"]])).data
        self.assertEqual(plan["evaluacion"]["resultado"], "SUPERADO")
        self.assertEqual(Dificultad.objects.get(estudiante=self.est1, tema=self.fracciones).estado, "SUPERADA")

    def test_ya_evaluado_no_recibe_otra_evaluacion(self):
        self.completar()
        actividad = self.publicar().data["id"]
        with self.captureOnCommitCallbacks(execute=True):
            self.calificar(actividad, [(self.est1, 8)])
        self.assertEqual(self.publicar().status_code, 400)  # ya no queda nadie pendiente
        # Pero la evaluación ya publicada lo sigue mostrando para corregir su nota.
        self.auth(self.doc1)
        filas = self.client.get(reverse("actividad-calificaciones", args=[actividad])).data["calificaciones"]
        self.assertEqual([f["estudiante"] for f in filas], [self.est1.id])

    def test_vista_previa_de_destinatarios(self):
        url = reverse("actividad-evaluacion-destinatarios")
        self.auth(self.doc1)
        params = {"paralelo": self.par_a.id, "asignatura": self.mate.id}
        self.assertEqual(self.client.get(url, params).data["estudiantes"], [])
        self.completar()
        self.auth(self.doc1)
        self.assertEqual([e["id"] for e in self.client.get(url, params).data["estudiantes"]], [self.est1.id])
        self.auth(self.doc3)  # no imparte en el paralelo A
        self.assertEqual(self.client.get(url, params).status_code, 400)

    def test_editar_para_marcarla_o_desmarcarla(self):
        actividad = self.publicar(es_evaluacion_refuerzo=False).data["id"]
        url = reverse("actividad-detail", args=[actividad])
        self.auth(self.doc1)
        self.assertEqual(self.client.patch(url, {"es_evaluacion_refuerzo": True}, format="json").status_code, 400)
        self.completar()
        self.auth(self.doc1)
        res = self.client.patch(url, {"es_evaluacion_refuerzo": True}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Actividad.objects.get(pk=actividad).destinatarios.count(), 1)
        res = self.client.patch(url, {"es_evaluacion_refuerzo": False}, format="json")
        self.assertEqual(Actividad.objects.get(pk=actividad).destinatarios.count(), 0)
        self.assertIn(actividad, self.ids_visibles(self.rep2))  # vuelve a ser de todo el paralelo
        # Con notas ya no se puede cambiar.
        self.auth(self.doc1)
        self.client.patch(url, {"es_evaluacion_refuerzo": True}, format="json")
        self.calificar(actividad, [(self.est1, 8)])
        self.auth(self.doc1)
        res = self.client.patch(url, {"es_evaluacion_refuerzo": False}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_migracion_asigna_destinatarios_a_evaluaciones_existentes(self):
        import importlib

        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        self.completar()
        vieja = Actividad.objects.create(
            asignacion=self.asig1, creada_por=self.doc1, descripcion="Evaluación antigua",
            fecha_entrega=HOY, es_evaluacion_refuerzo=True,
        )
        grades_services.guardar_calificaciones(vieja, self.fracciones, [(self.est3.id, Decimal("9"))], self.doc1)
        estado = MigrationLoader(connection).project_state(("activities", "0005_actividad_destinatarios"))
        importlib.import_module("apps.activities.migrations.0005_actividad_destinatarios").asignar_destinatarios(
            estado.apps, None
        )
        # Marta ya tenía nota (se conserva) y Luis tiene su plan completado pendiente.
        self.assertEqual(set(vieja.destinatarios.values_list("id", flat=True)), {self.est1.id, self.est3.id})
