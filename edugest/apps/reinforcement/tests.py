from datetime import date
from decimal import Decimal

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.academic.models import (
    Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo, Tema,
)
from apps.activities.models import Actividad
from apps.grades import services as grades_services
from apps.grades.models import Dificultad
from apps.security.models import Role, User
from apps.security.serializers import LoginSerializer

from .models import ActividadRefuerzo, PlanRefuerzo, RecursoRefuerzo
from .signals import (
    actividad_refuerzo_cumplida, plan_aprobado, plan_cancelado, plan_completado,
)

PASSWORD = "ClaveSegura2026"
HOY = date(2026, 10, 1)


def make_user(email, role, **extra):
    extra.setdefault("must_change_password", False)
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Nombre", last_name=email.split("@")[0],
        role=role, **extra,
    )


class RefuerzoBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user("admin@edugest.test", Role.ADMINISTRADOR)
        self.doc1 = make_user("doc1@edugest.test", Role.DOCENTE)   # Matemática en A
        self.doc2 = make_user("doc2@edugest.test", Role.DOCENTE)   # Lengua en A
        self.doc3 = make_user("doc3@edugest.test", Role.DOCENTE)   # Matemática en B
        self.rep1 = make_user("rep1@edugest.test", Role.REPRESENTANTE)
        self.rep2 = make_user("rep2@edugest.test", Role.REPRESENTANTE)

        self.grado7 = Grado.objects.create(nombre="Séptimo EGB", orden=7)
        self.par_a = Paralelo.objects.create(grado=self.grado7, nombre="A")
        self.par_b = Paralelo.objects.create(grado=self.grado7, nombre="B")
        self.mate = Asignatura.objects.create(nombre="Matemática")
        self.lengua = Asignatura.objects.create(nombre="Lengua y Literatura")

        self.asig1 = AsignacionDocente.objects.create(docente=self.doc1, paralelo=self.par_a, asignatura=self.mate)
        self.asig2 = AsignacionDocente.objects.create(docente=self.doc2, paralelo=self.par_a, asignatura=self.lengua)
        self.asig3 = AsignacionDocente.objects.create(docente=self.doc3, paralelo=self.par_b, asignatura=self.mate)

        self.est1 = Estudiante.objects.create(first_name="Luis", last_name="Pérez", paralelo=self.par_a, representante=self.rep1)
        self.est3 = Estudiante.objects.create(first_name="Marta", last_name="Vera", paralelo=self.par_a, representante=self.rep2)
        self.est2 = Estudiante.objects.create(first_name="Sofía", last_name="Mora", paralelo=self.par_b, representante=self.rep2)

        def tema(nombre, asignatura=None, padre=None):
            return Tema.objects.create(grado=self.grado7, asignatura=asignatura or self.mate, nombre=nombre, padre=padre)

        self.fracciones = tema("Fracciones")
        self.equivalentes = tema("Fracciones equivalentes", padre=self.fracciones)
        self.decimales = tema("Decimales")
        self.proporcion = tema("Proporcionalidad")
        self.comprension = tema("Comprensión lectora", asignatura=self.lengua)

        def recurso(t, nivel, titulo, **extra):
            return RecursoRefuerzo.objects.create(
                tema=t, nivel=nivel, titulo=titulo, instrucciones=f"Instrucciones de {titulo}",
                duracion_minutos=15, **extra,
            )

        self.b1 = recurso(self.fracciones, "BASICO", "Básica 1")
        self.b2 = recurso(self.fracciones, "BASICO", "Básica 2")
        self.b3 = recurso(self.fracciones, "BASICO", "Básica 3")
        self.i1 = recurso(self.fracciones, "INTERMEDIO", "Intermedia 1")
        self.i2 = recurso(self.fracciones, "INTERMEDIO", "Intermedia 2")
        self.i3 = recurso(self.fracciones, "INTERMEDIO", "Intermedia 3")
        self.a1 = recurso(self.fracciones, "AVANZADO", "Avanzada 1")
        self.db1 = recurso(self.decimales, "BASICO", "Decimal básica")
        self.di1 = recurso(self.decimales, "INTERMEDIO", "Decimal intermedia")
        self.rl1 = recurso(self.comprension, "BASICO", "Lectura básica")

        self.eventos = []
        for senal, nombre in (
            (plan_aprobado, "aprobado"), (plan_cancelado, "cancelado"),
            (actividad_refuerzo_cumplida, "cumplida"), (plan_completado, "completado"),
        ):
            self._conectar(senal, nombre)

    def _conectar(self, senal, nombre):
        def receptor(sender, **kwargs):
            plan = kwargs["plan"]
            self.eventos.append((nombre, plan.pk))

        senal.connect(receptor, weak=False)
        self.addCleanup(senal.disconnect, receptor)

    # --- utilidades --------------------------------------------------------
    def auth(self, user):
        token = LoginSerializer.get_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def post(self, url, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, data or {}, format="json")

    def patch(self, url, data):
        return self.client.patch(url, data, format="json")

    def dar_nota(self, estudiante, tema, valor, asignacion=None):
        """Registra una nota (con una actividad nueva) para provocar dificultades reales."""
        asignacion = asignacion or (self.asig2 if tema.asignatura_id == self.lengua.id else self.asig1)
        actividad = Actividad.objects.create(
            asignacion=asignacion, creada_por=asignacion.docente, descripcion=f"Tarea {Actividad.objects.count()}",
            fecha_entrega=HOY,
        )
        grades_services.guardar_calificaciones(
            actividad, tema, [(estudiante.id, Decimal(str(valor)))], asignacion.docente
        )

    def generar(self, estudiante=None, asignatura=None, user=None):
        self.auth(user or self.doc1)
        return self.post(
            reverse("plan-generar"),
            {"estudiante": (estudiante or self.est1).id, "asignatura": (asignatura or self.mate).id},
        )

    def plan_con(self, notas):
        """Crea las dificultades indicadas {tema: nota} para est1 y genera el plan."""
        for tema, nota in notas.items():
            self.dar_nota(self.est1, tema, nota)
        res = self.generar()
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    @staticmethod
    def titulos(tema_plan):
        return [a["titulo"] for a in tema_plan["actividades"]]

    @staticmethod
    def ids(response):
        return sorted(item["id"] for item in response.data["results"])


# ---------------------------------------------------------------------------
class GenerarPlanTests(RefuerzoBase):
    def test_aplica_las_reglas_del_motor(self):
        plan = self.plan_con({self.fracciones: "3.5", self.decimales: "6.0"})
        self.assertEqual((plan["estado"], plan["nivel"], plan["docente"]), ("PROPUESTA", "ALTO", self.doc1.id))
        self.assertEqual(plan["asignatura_nombre"], "Matemática")

        frac, dec = plan["temas"]
        # Primero el tema con menor promedio.
        self.assertEqual((frac["tema_nombre"], frac["orden"], frac["nivel_dificultad"]), ("Fracciones", 1, "ALTA"))
        self.assertEqual(frac["promedio_inicial"], "3.50")
        self.assertEqual(frac["objetivo"], "Mejorar el desempeño en «Fracciones» de Matemática, llevando el promedio actual de 3,50 a 7,00 o más.")
        # Dificultad ALTA: 2 básicas + 2 intermedias.
        self.assertEqual(self.titulos(frac), ["Básica 1", "Básica 2", "Intermedia 1", "Intermedia 2"])
        # Dificultad MODERADA: 1 básica + 2 intermedias (el banco solo tiene 1 intermedia).
        self.assertEqual(dec["nivel_dificultad"], "MODERADA")
        self.assertEqual(self.titulos(dec), ["Decimal básica", "Decimal intermedia"])

        self.assertEqual(
            plan["avance"],
            {"actividades_total": 6, "actividades_cumplidas": 0, "porcentaje": 0, "temas_total": 2, "temas_superados": 0},
        )

    def test_las_actividades_copian_el_contenido_del_recurso(self):
        plan = self.plan_con({self.fracciones: "3.5"})
        actividad = plan["temas"][0]["actividades"][0]
        self.assertEqual(
            (actividad["origen"], actividad["nivel"], actividad["estado"], actividad["duracion_minutos"]),
            ("BANCO", "BASICO", "PENDIENTE", 15),
        )
        # Editar el banco después no altera el plan.
        self.b1.titulo = "Cambiado"
        self.b1.save()
        self.auth(self.doc1)
        res = self.client.get(reverse("plan-detail", args=[plan["id"]]))
        self.assertEqual(res.data["temas"][0]["actividades"][0]["titulo"], "Básica 1")

    def test_maximo_tres_temas_los_de_menor_promedio(self):
        plan = self.plan_con({
            self.fracciones: "3.0", self.equivalentes: "4.5", self.decimales: "5.5", self.proporcion: "6.5",
        })
        self.assertEqual(
            [t["tema_nombre"] for t in plan["temas"]],
            ["Fracciones", "Fracciones equivalentes", "Decimales"],
        )

    def test_nivel_regular_si_no_hay_dificultad_alta(self):
        plan = self.plan_con({self.decimales: "6.0"})
        self.assertEqual(plan["nivel"], "REGULAR")

    def test_tema_sin_recursos_se_incluye_marcado(self):
        plan = self.plan_con({self.proporcion: "5.0"})
        tema = plan["temas"][0]
        self.assertTrue(tema["sin_recursos"])
        self.assertEqual(tema["actividades"], [])

    def test_un_subtema_sin_recursos_usa_los_de_su_tema_padre(self):
        plan = self.plan_con({self.equivalentes: "5.0"})
        tema = plan["temas"][0]
        self.assertFalse(tema["sin_recursos"])
        # MODERADA: 1 básica + 2 intermedias, tomadas de «Fracciones».
        self.assertEqual(self.titulos(tema), ["Básica 1", "Intermedia 1", "Intermedia 2"])

    def test_un_segundo_plan_prefiere_recursos_que_el_estudiante_no_recibio(self):
        plan = self.plan_con({self.fracciones: "3.5"})
        self.post(reverse("plan-cancelar", args=[plan["id"]]))
        res = self.generar()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(self.titulos(res.data["temas"][0]), ["Básica 3", "Básica 1", "Intermedia 3", "Intermedia 1"])

    def test_solo_cuentan_las_dificultades_detectadas_de_la_asignatura(self):
        self.dar_nota(self.est1, self.fracciones, "9.0")      # sin dificultad
        self.dar_nota(self.est1, self.comprension, "3.0")     # dificultad en Lengua
        res = self.generar()
        self.assertEqual(res.status_code, 400)
        self.assertIn("no tiene dificultades", res.data["detail"])

    def test_solo_un_plan_vigente_por_estudiante_y_asignatura(self):
        self.plan_con({self.fracciones: "3.5"})
        res = self.generar()
        self.assertEqual(res.status_code, 400)
        self.assertIn("Ya existe un plan", res.data["detail"])

    def test_tras_cancelar_se_puede_generar_otro(self):
        plan = self.plan_con({self.fracciones: "3.5"})
        self.post(reverse("plan-cancelar", args=[plan["id"]]))
        self.assertEqual(self.generar().status_code, 201)
        self.assertEqual(PlanRefuerzo.objects.count(), 2)

    def test_docente_que_no_imparte_la_asignatura(self):
        self.dar_nota(self.est1, self.fracciones, "3.5")
        res = self.generar(user=self.doc2)   # doc2 da Lengua en A: ve al estudiante, no Matemática
        self.assertEqual(res.status_code, 400)
        self.assertIn("asignatura", res.data)

    def test_estudiante_de_otro_paralelo_no_se_encuentra(self):
        res = self.generar(estudiante=self.est2)   # doc1 solo da clases en A
        self.assertEqual(res.status_code, 404)

    def test_estudiante_inactivo(self):
        self.dar_nota(self.est1, self.fracciones, "3.5")
        self.est1.is_active = False
        self.est1.save()
        self.assertEqual(self.generar().status_code, 400)

    def test_datos_invalidos(self):
        self.auth(self.doc1)
        self.assertEqual(self.post(reverse("plan-generar"), {"estudiante": self.est1.id}).status_code, 400)
        self.assertEqual(self.post(reverse("plan-generar"), {"estudiante": self.est1.id, "asignatura": 9999}).status_code, 400)

    def test_solo_docentes_generan(self):
        for user in (self.rep1, self.admin):
            self.assertEqual(self.generar(user=user).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.post(reverse("plan-generar"), {}).status_code, 401)


# ---------------------------------------------------------------------------
class EdicionTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.tema_plan = self.plan["temas"][0]
        self.url_tema = reverse("tema-plan-detail", args=[self.tema_plan["id"]])
        self.url_agregar = reverse("tema-plan-agregar-actividad", args=[self.tema_plan["id"]])
        self.actividad_id = self.tema_plan["actividades"][0]["id"]
        self.url_act = reverse("actividad-refuerzo-detail", args=[self.actividad_id])

    def test_editar_objetivo(self):
        res = self.patch(self.url_tema, {"objetivo": "  Dominar   las fracciones  "})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["objetivo"], "Dominar las fracciones")
        self.assertEqual(self.patch(self.url_tema, {"objetivo": "   "}).status_code, 400)

    def test_agregar_actividad_del_banco(self):
        res = self.post(self.url_agregar, {"recurso": self.a1.id})
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.data["origen"], res.data["nivel"], res.data["titulo"]), ("BANCO", "AVANZADO", "Avanzada 1"))
        self.assertEqual(self.post(self.url_agregar, {"recurso": self.a1.id}).status_code, 400)  # repetida

    def test_recurso_de_otra_asignatura_o_inactivo(self):
        self.assertEqual(self.post(self.url_agregar, {"recurso": self.rl1.id}).status_code, 400)
        self.a1.is_active = False
        self.a1.save()
        self.assertEqual(self.post(self.url_agregar, {"recurso": self.a1.id}).status_code, 400)

    def test_agregar_actividad_propia(self):
        res = self.post(self.url_agregar, {"titulo": "Repasar en casa", "instrucciones": "Resolver la página 30", "duracion_minutos": 20})
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.data["origen"], res.data["recurso"], res.data["nivel"]), ("MANUAL", None, ""))
        self.assertEqual(res.data["orden"], 5)

    def test_actividad_propia_incompleta(self):
        self.assertEqual(self.post(self.url_agregar, {"titulo": "Solo título"}).status_code, 400)
        self.assertEqual(self.post(self.url_agregar, {}).status_code, 400)

    def test_editar_y_quitar_actividades(self):
        res = self.patch(self.url_act, {"titulo": "Nuevo título", "duracion_minutos": 30})
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["titulo"], res.data["duracion_minutos"]), ("Nuevo título", 30))

        res = self.client.delete(self.url_act)
        self.assertEqual(res.status_code, 204)
        self.assertFalse(ActividadRefuerzo.objects.filter(pk=self.actividad_id).exists())

    def test_cambiar_una_actividad_es_quitar_y_agregar(self):
        self.client.delete(self.url_act)
        res = self.post(self.url_agregar, {"recurso": self.b3.id})
        self.assertEqual(res.status_code, 201)

    def test_maximo_de_actividades_por_tema(self):
        for i in range(6):   # ya tiene 4 -> llega a 10
            self.assertEqual(self.post(self.url_agregar, {"titulo": f"Extra {i}", "instrucciones": "x"}).status_code, 201)
        res = self.post(self.url_agregar, {"titulo": "Una más", "instrucciones": "x"})
        self.assertEqual(res.status_code, 400)

    def test_aprobado_el_plan_ya_no_se_edita(self):
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        self.assertEqual(self.patch(self.url_tema, {"objetivo": "Otro"}).status_code, 400)
        self.assertEqual(self.post(self.url_agregar, {"recurso": self.a1.id}).status_code, 400)
        self.assertEqual(self.patch(self.url_act, {"titulo": "Otro"}).status_code, 400)
        self.assertEqual(self.client.delete(self.url_act).status_code, 400)

    def test_otro_docente_no_lo_encuentra(self):
        self.auth(self.doc2)
        self.assertEqual(self.patch(self.url_tema, {"objetivo": "Otro"}).status_code, 404)
        self.assertEqual(self.post(self.url_agregar, {"recurso": self.a1.id}).status_code, 404)
        self.assertEqual(self.patch(self.url_act, {"titulo": "Otro"}).status_code, 404)

    def test_representante_y_admin_no_editan(self):
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.patch(self.url_tema, {"objetivo": "Otro"}).status_code, 403)
            self.assertEqual(self.client.delete(self.url_act).status_code, 403)


# ---------------------------------------------------------------------------
class AprobacionTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.url_aprobar = reverse("plan-aprobar", args=[self.plan["id"]])
        self.url_cancelar = reverse("plan-cancelar", args=[self.plan["id"]])

    def test_aprobar_publica_el_plan_y_emite_evento(self):
        res = self.post(self.url_aprobar)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["estado"], "APROBADA")
        self.assertIsNotNone(res.data["aprobado_en"])
        plan = PlanRefuerzo.objects.get(pk=self.plan["id"])
        self.assertEqual(plan.aprobado_por, self.doc1)
        self.assertEqual(self.eventos, [("aprobado", plan.pk)])
        self.assertEqual(self.post(self.url_aprobar).status_code, 400)   # dos veces

    def test_no_se_aprueba_un_plan_sin_actividades(self):
        ActividadRefuerzo.objects.all().delete()
        res = self.post(self.url_aprobar)
        self.assertEqual(res.status_code, 400)
        self.assertIn("sin actividades".replace("sin ", "no tiene "), res.data["detail"])

    def test_el_representante_solo_ve_el_plan_una_vez_aprobado(self):
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("plan-list")).data["count"], 0)
        self.assertEqual(self.client.get(reverse("plan-detail", args=[self.plan["id"]])).status_code, 404)

        self.auth(self.doc1)
        self.post(self.url_aprobar)

        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("plan-list")).data["count"], 1)
        self.assertEqual(self.client.get(reverse("plan-detail", args=[self.plan["id"]])).status_code, 200)
        # El otro representante no lo ve.
        self.auth(self.rep2)
        self.assertEqual(self.client.get(reverse("plan-list")).data["count"], 0)

    def test_cancelar_una_propuesta_no_la_muestra_a_la_familia(self):
        res = self.post(self.url_cancelar)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["estado"], "CANCELADA")
        self.assertEqual(self.eventos, [("cancelado", self.plan["id"])])
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("plan-list")).data["count"], 0)

    def test_cancelar_un_plan_aprobado_sigue_visible_para_la_familia(self):
        self.post(self.url_aprobar)
        self.assertEqual(self.post(self.url_cancelar).status_code, 200)
        self.auth(self.rep1)
        res = self.client.get(reverse("plan-list"))
        self.assertEqual([p["estado"] for p in res.data["results"]], ["CANCELADA"])

    def test_no_se_cancela_un_plan_cancelado_ni_completado(self):
        self.post(self.url_cancelar)
        self.assertEqual(self.post(self.url_cancelar).status_code, 400)

    def test_otro_docente_y_otros_roles(self):
        self.auth(self.doc2)
        self.assertEqual(self.post(self.url_aprobar).status_code, 404)
        self.assertEqual(self.post(self.url_cancelar).status_code, 404)
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.post(self.url_aprobar).status_code, 403)


# ---------------------------------------------------------------------------
class SeguimientoTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.ids_act = [a["id"] for a in self.plan["temas"][0]["actividades"]]

    def aprobar(self):
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))
        self.eventos.clear()

    def cumplir(self, user, actividad_id):
        self.auth(user)
        return self.post(reverse("actividad-refuerzo-cumplir", args=[actividad_id]))

    def test_el_representante_marca_y_queda_registrado(self):
        self.aprobar()
        res = self.cumplir(self.rep1, self.ids_act[0])
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["estado"], res.data["cumplida_por"], res.data["plan_estado"]),
                         ("CUMPLIDA", self.rep1.id, "APROBADA"))
        self.assertIsNotNone(res.data["cumplida_en"])
        self.assertEqual(self.eventos, [("cumplida", self.plan["id"])])

    def test_el_docente_tambien_puede_marcar(self):
        self.aprobar()
        res = self.cumplir(self.doc1, self.ids_act[0])
        self.assertEqual(res.data["cumplida_por"], self.doc1.id)

    def test_no_se_marca_en_una_propuesta(self):
        self.assertEqual(self.cumplir(self.doc1, self.ids_act[0]).status_code, 400)
        # Y la familia ni siquiera la encuentra.
        self.assertEqual(self.cumplir(self.rep1, self.ids_act[0]).status_code, 404)

    def test_otro_representante_otro_docente_y_admin(self):
        self.aprobar()
        self.assertEqual(self.cumplir(self.rep2, self.ids_act[0]).status_code, 404)
        self.assertEqual(self.cumplir(self.doc2, self.ids_act[0]).status_code, 404)
        self.assertEqual(self.cumplir(self.admin, self.ids_act[0]).status_code, 403)

    def test_marcar_dos_veces(self):
        self.aprobar()
        self.cumplir(self.rep1, self.ids_act[0])
        self.assertEqual(self.cumplir(self.rep1, self.ids_act[0]).status_code, 400)

    def test_completar_todas_cierra_el_plan(self):
        self.aprobar()
        for actividad_id in self.ids_act[:-1]:
            self.cumplir(self.rep1, actividad_id)
        self.assertEqual(PlanRefuerzo.objects.get().estado, "APROBADA")

        res = self.cumplir(self.rep1, self.ids_act[-1])
        self.assertEqual(res.data["plan_estado"], "COMPLETADA")
        plan = PlanRefuerzo.objects.get()
        self.assertIsNotNone(plan.completado_en)
        self.assertEqual([e[0] for e in self.eventos].count("completado"), 1)

        self.auth(self.rep1)
        detalle = self.client.get(reverse("plan-detail", args=[plan.id]))
        self.assertEqual(detalle.data["avance"]["porcentaje"], 100)
        # Un plan completado ya no se cancela ni admite más marcas.
        self.auth(self.doc1)
        self.assertEqual(self.post(reverse("plan-cancelar", args=[plan.id])).status_code, 400)

    def test_solo_el_docente_reabre_y_el_plan_vuelve_a_aprobado(self):
        self.aprobar()
        for actividad_id in self.ids_act:
            self.cumplir(self.rep1, actividad_id)
        self.assertEqual(PlanRefuerzo.objects.get().estado, "COMPLETADA")

        url = reverse("actividad-refuerzo-reabrir", args=[self.ids_act[0]])
        self.auth(self.rep1)
        self.assertEqual(self.post(url).status_code, 403)

        self.auth(self.doc1)
        res = self.post(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data["estado"], res.data["plan_estado"]), ("PENDIENTE", "APROBADA"))
        self.assertIsNone(res.data["cumplida_por"])
        plan = PlanRefuerzo.objects.get()
        self.assertEqual(plan.estado, "APROBADA")
        self.assertIsNone(plan.completado_en)
        self.assertEqual(self.post(url).status_code, 400)   # ya está pendiente

    def test_un_plan_cancelado_no_admite_marcas(self):
        self.aprobar()
        self.auth(self.doc1)
        self.post(reverse("plan-cancelar", args=[self.plan["id"]]))
        self.assertEqual(self.cumplir(self.rep1, self.ids_act[0]).status_code, 400)

    def test_el_avance_incluye_los_temas_superados_segun_las_notas_nuevas(self):
        self.aprobar()
        self.cumplir(self.rep1, self.ids_act[0])
        # Tras el refuerzo, el docente corrige la nota y la dificultad queda superada.
        self.dar_nota(self.est1, self.fracciones, "10")   # (3.5 + 10) / 2 = 6.75 -> sigue
        self.dar_nota(self.est1, self.fracciones, "10")   # (3.5 + 10 + 10) / 3 = 7.83 -> superada
        self.assertEqual(Dificultad.objects.get().estado, "SUPERADA")
        self.auth(self.rep1)
        avance = self.client.get(reverse("plan-detail", args=[self.plan["id"]])).data["avance"]
        self.assertEqual(
            avance,
            {"actividades_total": 4, "actividades_cumplidas": 1, "porcentaje": 25, "temas_total": 1, "temas_superados": 1},
        )


# ---------------------------------------------------------------------------
class VisibilidadPlanesTests(RefuerzoBase):
    url = "/api/reinforcement/planes/"

    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})

    def test_docente_que_imparte_la_asignatura_lo_ve_y_otros_no(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        for otro in (self.doc2, self.doc3):   # Lengua en A / Matemática en B
            self.auth(otro)
            self.assertEqual(self.client.get(self.url).data["count"], 0)
            self.assertEqual(self.client.get(f"{self.url}{self.plan['id']}/").status_code, 404)

    def test_administrador_consulta(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url).data["count"], 1)

    def test_filtros(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.get(self.url, {"estado": "propuesta"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"estado": "APROBADA"}).data["count"], 0)
        self.assertEqual(self.client.get(self.url, {"estudiante": self.est1.id}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"estudiante": self.est3.id}).data["count"], 0)
        self.assertEqual(self.client.get(self.url, {"asignatura": self.mate.id}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"paralelo": self.par_b.id}).data["count"], 0)
        self.assertEqual(self.client.get(self.url, {"estado": "otro"}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"estudiante": "x"}).status_code, 400)

    def test_requiere_autenticacion_y_clave_definitiva(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        temporal = make_user("temp@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(temporal)
        self.assertEqual(self.client.get(self.url).status_code, 403)


# ---------------------------------------------------------------------------
class RecursoTests(RefuerzoBase):
    url = "/api/reinforcement/recursos/"

    def datos(self, **cambios):
        datos = {
            "tema": self.fracciones.id, "nivel": "AVANZADO", "titulo": "Desafío de fracciones",
            "instrucciones": "Resuelve el desafío.", "duracion_minutos": 30,
        }
        datos.update(cambios)
        return datos

    def test_docente_crea_en_lo_que_imparte(self):
        self.auth(self.doc1)
        res = self.post(self.url, self.datos())
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.data["creado_por"], res.data["asignatura_nombre"], res.data["grado_nombre"]),
                         (self.doc1.id, "Matemática", "Séptimo EGB"))

    def test_docente_no_crea_en_asignaturas_que_no_imparte(self):
        self.auth(self.doc1)
        res = self.post(self.url, self.datos(tema=self.comprension.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn("tema", res.data)

    def test_administrador_crea_en_cualquier_tema(self):
        self.auth(self.admin)
        res = self.post(self.url, self.datos(tema=self.comprension.id))
        self.assertEqual(res.status_code, 201)

    def test_representante_no_accede(self):
        self.auth(self.rep1)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.post(self.url, self.datos()).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_el_docente_ve_el_banco_de_sus_asignaturas_y_grados(self):
        self.auth(self.doc1)
        res = self.client.get(self.url)
        self.assertEqual(res.data["count"], 9)   # todo Matemática; nada de Lengua
        self.auth(self.doc2)
        self.assertEqual(self.client.get(self.url).data["count"], 1)

    def test_titulo_repetido_sin_importar_mayusculas(self):
        self.auth(self.doc1)
        self.assertEqual(self.post(self.url, self.datos(titulo="BÁSICA 1", nivel="BASICO")).status_code, 400)

    def test_solo_el_autor_o_el_admin_editan(self):
        self.auth(self.doc1)
        creado = self.post(self.url, self.datos()).data

        self.auth(self.doc3)   # misma asignatura (Matemática), otro docente
        self.assertEqual(self.client.get(f"{self.url}{creado['id']}/").status_code, 200)
        self.assertEqual(self.patch(f"{self.url}{creado['id']}/", {"titulo": "Robado"}).status_code, 403)

        self.auth(self.doc1)
        self.assertEqual(self.patch(f"{self.url}{creado['id']}/", {"titulo": "Mejorado"}).status_code, 200)
        self.auth(self.admin)
        self.assertEqual(self.patch(f"{self.url}{creado['id']}/", {"is_active": False}).status_code, 200)

    def test_el_tema_no_se_cambia_y_no_hay_borrado(self):
        self.auth(self.admin)
        self.assertEqual(self.patch(f"{self.url}{self.b1.id}/", {"tema": self.decimales.id}).status_code, 400)
        self.assertEqual(self.client.delete(f"{self.url}{self.b1.id}/").status_code, 405)

    def test_filtros(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url, {"nivel": "basico"}).data["count"], 5)
        self.assertEqual(self.client.get(self.url, {"tema": self.decimales.id}).data["count"], 2)
        self.assertEqual(self.client.get(self.url, {"asignatura": self.lengua.id}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"search": "decimal"}).data["count"], 2)
        self.assertEqual(self.client.get(self.url, {"nivel": "otro"}).status_code, 400)

    def test_duracion_fuera_de_rango(self):
        self.auth(self.doc1)
        self.assertEqual(self.post(self.url, self.datos(duracion_minutos=0)).status_code, 400)
        self.assertEqual(self.post(self.url, self.datos(duracion_minutos=500)).status_code, 400)


# ---------------------------------------------------------------------------
class SeedTests(APITestCase):
    def test_falla_si_faltan_los_temas(self):
        call_command("seed_academico", verbosity=0)
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_banco_refuerzo", verbosity=0)
        self.assertIn("seed_temas_ejemplo", str(ctx.exception))

    def test_es_idempotente(self):
        call_command("seed_academico", verbosity=0)
        call_command("seed_temas_ejemplo", verbosity=0)
        call_command("seed_banco_refuerzo", verbosity=0)
        total = RecursoRefuerzo.objects.count()
        self.assertGreater(total, 10)
        call_command("seed_banco_refuerzo", verbosity=0)
        self.assertEqual(RecursoRefuerzo.objects.count(), total)
