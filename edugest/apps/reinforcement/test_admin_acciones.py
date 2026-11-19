"""
Acciones de estado del admin de Django: aplican las mismas reglas que la app.
Se prueban de punta a punta, como las usa el administrador (lista -> acción -> «Ir»).
"""

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

from apps.academic.models import Paralelo, Tema
from apps.security.models import EnvioAcceso, Role, User

from .models import PlanRefuerzo
from .tests import RefuerzoBase


# Las páginas del admin cargan su CSS; en pruebas no hay «collectstatic».
SIN_MANIFIESTO = {**settings.STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


@override_settings(STORAGES=SIN_MANIFIESTO)
class AccionesEstadoAdminTests(RefuerzoBase):
    def tema(self, nombre, padre=None):
        return Tema.objects.create(grado=self.grado7, asignatura=self.mate, nombre=nombre, padre=padre)

    def setUp(self):
        super().setUp()
        self.su = User.objects.create_superuser(
            email="root@edugest.test", password="Clave-Segura-123", first_name="Root", last_name="Admin",
            role=Role.ADMINISTRADOR,
        )
        self.client.force_login(self.su)

    def accion(self, modelo, accion, *objetos):
        url = reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_changelist")
        res = self.client.post(
            url, {"action": accion, "_selected_action": [o.pk for o in objetos]}, follow=True
        )
        self.assertEqual(res.status_code, 200)
        return " | ".join(str(m) for m in get_messages(res.wsgi_request))

    def acciones_de(self, modelo):
        url = reverse(f"admin:{modelo._meta.app_label}_{modelo._meta.model_name}_changelist")
        formulario = self.client.get(url).context["action_form"]
        return formulario.fields["action"].choices if formulario else []  # sin acciones: no hay selector

    def test_las_tablas_con_activo_tienen_activar_y_desactivar(self):
        for modelo in (Paralelo, Tema, User):
            nombres = [n for n, _ in self.acciones_de(modelo)]
            self.assertIn("activar_seleccionados", nombres, modelo)
            self.assertIn("desactivar_seleccionados", nombres, modelo)

    def test_paralelo_respeta_las_reglas_de_la_app(self):
        vacio = Paralelo.objects.create(grado=self.grado7, nombre="C")
        texto = self.accion(Paralelo, "desactivar_seleccionados", self.par_a, vacio)
        self.assertIn("desactivados: 1", texto)
        self.assertIn("estudiantes activos", texto)  # el A tiene estudiantes: se omite
        self.par_a.refresh_from_db()
        vacio.refresh_from_db()
        self.assertEqual((self.par_a.is_active, vacio.is_active), (True, False))
        self.assertIn("activados: 1", self.accion(Paralelo, "activar_seleccionados", vacio))
        self.assertIn("ya estaban así", self.accion(Paralelo, "activar_seleccionados", vacio))

    def test_tema_con_subtemas_activos_no_se_desactiva(self):
        padre = self.fracciones  # tiene el subtema «Fracciones equivalentes»
        self.assertIn("subtemas activos", self.accion(Tema, "desactivar_seleccionados", padre))
        padre.refresh_from_db()
        self.assertTrue(padre.is_active)

    def test_usuario_cierra_sesiones_y_no_se_desactiva_a_si_mismo(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
        from rest_framework_simplejwt.tokens import RefreshToken

        RefreshToken.for_user(self.doc1)
        texto = self.accion(User, "desactivar_seleccionados", self.doc1, self.su)
        self.assertIn("desactivados: 1", texto)
        self.assertIn("tu propia cuenta", texto)
        self.doc1.refresh_from_db()
        self.assertFalse(self.doc1.is_active)
        self.assertTrue(BlacklistedToken.objects.filter(token__user=self.doc1).exists())

    def test_cancelar_planes_con_la_logica_de_la_app(self):
        plan = PlanRefuerzo.objects.get(pk=self.plan_con({self.fracciones: 5})["id"])
        self.assertIn("cancelados: 1", self.accion(PlanRefuerzo, "cancelar_planes", plan))
        plan.refresh_from_db()
        self.assertEqual(plan.estado, "CANCELADA")
        self.assertIsNotNone(plan.cancelado_en)
        # Un plan ya cancelado (o completado) no se puede cancelar: se informa el motivo.
        self.assertIn("propuesta o aprobado", self.accion(PlanRefuerzo, "cancelar_planes", plan))
        nombres = [n for n, _ in self.acciones_de(PlanRefuerzo)]
        self.assertEqual(nombres[1:], ["cancelar_planes"])  # nada de aprobar/completar a mano

    def test_cola_de_correos_reintentar_y_cancelar(self):
        nuevo = User.objects.create_user(
            email="nuevo@edugest.test", password=None, first_name="Ana", last_name="Nueva",
            role=Role.DOCENTE, must_change_password=True,
        )
        fallido = EnvioAcceso.objects.create(usuario=nuevo, lote="x", estado="ERROR", intentos=3, ultimo_error="403")
        enviado = EnvioAcceso.objects.create(usuario=self.doc1, lote="x", estado="ENVIADO")
        texto = self.accion(EnvioAcceso, "reintentar_envios", fallido, enviado)
        self.assertIn("de vuelta en la cola: 1", texto)
        self.assertIn("Enviado", texto)  # el enviado no se toca
        fallido.refresh_from_db()
        self.assertEqual(fallido.intentos, 0 if fallido.estado == "PENDIENTE" else fallido.intentos)
        self.assertNotEqual(fallido.estado, "ERROR")

        pendiente = EnvioAcceso.objects.create(usuario=nuevo, lote="y")
        self.assertIn("cancelados: 1", self.accion(EnvioAcceso, "cancelar_envios", pendiente))
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, "CANCELADO")

    def test_dificultades_y_notificaciones_no_tienen_acciones_de_estado(self):
        from apps.grades.models import Dificultad
        from apps.notifications.models import Notificacion

        for modelo in (Dificultad, Notificacion):
            nombres = [n for n, _ in self.acciones_de(modelo)]
            self.assertFalse([n for n in nombres if "estado" in n or "activar" in n], modelo)
