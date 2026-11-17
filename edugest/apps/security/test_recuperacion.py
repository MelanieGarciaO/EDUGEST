"""
Contraseñas: el correo es el único canal de las claves temporales.
- Alta por el admin (la temporal llega solo por correo) y reenvío del acceso.
- «¿Olvidaste tu contraseña?»: código OTP por correo -> temporal en pantalla -> contraseña nueva.
- Cambio desde el Perfil: clave temporal por correo -> contraseña nueva.
"""

import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APITransactionTestCase

from apps.notifications.models import Notificacion

from .models import CodigoRecuperacion, Role, User

CLAVE = "ClaveSegura123"
NUEVA = "MiNuevaClave2026!"


def codigo_del_correo(correo):
    return re.search(r"\b(\d{6})\b", correo.body).group(1)


def temporal_del_correo(correo):
    return re.search(r"^\s{4}(\S{12})\s*$", correo.body, re.M).group(1)


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ana@edugest.test", CLAVE, first_name="Ana", last_name="Ruiz",
                                             role=Role.DOCENTE, must_change_password=False)
        mail.outbox.clear()

    def post(self, *args, **kwargs):
        # Los correos salen al confirmar la transacción (on_commit): se ejecuta aquí.
        kwargs.setdefault("format", "json")
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)

    def login(self, password, email="ana@edugest.test"):
        return self.client.post(reverse("login"), {"email": email, "password": password}, format="json")


# ---------------------------------------------------------------------------
# «¿Olvidaste tu contraseña?»
# ---------------------------------------------------------------------------
class RecuperacionTests(Base):
    def solicitar(self, email="ana@edugest.test", ip="10.0.0.1"):
        return self.post(reverse("recuperar-solicitar"), {"email": email}, REMOTE_ADDR=ip)

    def verificar(self, codigo, email="ana@edugest.test"):
        return self.post(reverse("recuperar-verificar"), {"email": email, "codigo": codigo})

    def restablecer(self, temporal, nueva=NUEVA, email="ana@edugest.test"):
        return self.post(reverse("recuperar-restablecer"),
                         {"email": email, "clave_temporal": temporal, "new_password": nueva})

    def temporal(self):
        self.solicitar()
        return self.verificar(codigo_del_correo(mail.outbox[-1])).data["temporary_password"]

    def test_flujo_completo_en_el_mismo_recuperador(self):
        self.assertEqual(self.solicitar("ANA@edugest.test").status_code, 200)
        [correo] = mail.outbox
        self.assertIn("código", correo.subject)
        codigo = codigo_del_correo(correo)
        # El código no se guarda en claro y el aviso en la app no lo contiene.
        self.assertNotIn(codigo, CodigoRecuperacion.objects.get().codigo_hash)
        self.assertNotIn(codigo, Notificacion.objects.get(tipo="recuperacion_codigo").mensaje)

        # Código correcto: la temporal se muestra en pantalla y NO se envía por correo.
        res = self.verificar(f"{codigo[:3]} {codigo[3:]}")  # acepta espacios
        self.assertEqual(res.status_code, 200, res.data)
        temporal = res.data["temporary_password"]
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(Notificacion.objects.filter(mensaje__contains=temporal).exists())

        # En la misma pantalla crea la contraseña nueva y queda con sesión abierta.
        res = self.restablecer(temporal)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(res.data["access"] and res.data["refresh"])
        self.assertFalse(res.data["user"]["must_change_password"])
        self.assertIn("actualizó", mail.outbox[-1].subject)
        self.assertEqual(self.login(NUEVA).status_code, 200)
        self.assertNotEqual(self.login(temporal).status_code, 200)

        # Ni el código ni la temporal sirven otra vez.
        self.assertEqual(self.verificar(codigo).status_code, 400)
        self.assertEqual(self.restablecer(temporal, "OtraClave2026!!").status_code, 400)

    def test_si_cierra_el_recuperador_entra_con_la_temporal_y_crea_su_clave(self):
        temporal = self.temporal()
        login = self.login(temporal)
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = self.post(reverse("change-password"), {"clave_temporal": temporal, "new_password": NUEVA})
        self.assertEqual(res.status_code, 200, res.data)

    def test_restablecer_valida_la_temporal_y_la_clave_nueva(self):
        self.assertEqual(self.restablecer(CLAVE).status_code, 400)  # sin verificar código: no aplica
        temporal = self.temporal()
        self.assertIn("clave_temporal", self.restablecer("OtraCualquiera1").data)
        self.assertIn("new_password", self.restablecer(temporal, temporal).data)  # igual a la temporal
        self.assertIn("new_password", self.restablecer(temporal, "12345678").data)  # débil
        self.assertEqual(self.restablecer(temporal, email="otra@edugest.test").status_code, 400)
        self.assertEqual(self.restablecer(temporal).status_code, 200)

    def test_no_revela_si_el_correo_existe(self):
        existe = self.solicitar()
        cache.clear()
        no_existe = self.solicitar("nadie@edugest.test")
        self.assertEqual(existe.data, no_existe.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_cuenta_inactiva_no_recibe_codigo(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_intentos_limitados(self):
        self.solicitar()
        codigo = codigo_del_correo(mail.outbox[0])
        incorrecto = "000000" if codigo != "000000" else "111111"
        for restantes in (4, 3, 2, 1):
            self.assertIn(f"Te quedan {restantes}", str(self.verificar(incorrecto).data["codigo"]))
        self.assertIn("agotaron", str(self.verificar(incorrecto).data["codigo"]))
        self.assertEqual(self.verificar(codigo).status_code, 400)  # anulado aunque sea el correcto
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CLAVE))

    def test_codigo_vencido(self):
        self.solicitar()
        codigo = codigo_del_correo(mail.outbox[0])
        CodigoRecuperacion.objects.update(expira_en=timezone.now() - timedelta(seconds=1))
        self.assertIn("venció", str(self.verificar(codigo).data["codigo"]))

    @override_settings(RECUPERACION_ESPERA_SEGUNDOS=0)
    def test_codigo_nuevo_anula_el_anterior(self):
        self.solicitar()
        primero = codigo_del_correo(mail.outbox[0])
        self.solicitar()
        segundo = codigo_del_correo(mail.outbox[1])
        if primero != segundo:
            self.assertEqual(self.verificar(primero).status_code, 400)
        self.assertEqual(self.verificar(segundo).status_code, 200)

    def test_espera_entre_solicitudes_y_limite_por_hora(self):
        self.assertEqual(self.solicitar().status_code, 200)
        self.assertEqual(self.solicitar().status_code, 429)  # espera de 60 s
        with override_settings(RECUPERACION_ESPERA_SEGUNDOS=0):
            cache.delete("recuperar:espera:ana@edugest.test")
            for _ in range(4):
                self.assertEqual(self.solicitar().status_code, 200)
            self.assertEqual(self.solicitar().status_code, 429)  # 5 por hora

    def test_validaciones(self):
        self.assertEqual(self.solicitar("").status_code, 400)
        self.assertEqual(self.verificar("12345").status_code, 400)
        self.assertEqual(self.verificar("abcdef").status_code, 400)
        self.assertEqual(self.verificar("123456", email="nadie@edugest.test").status_code, 400)

    def test_verificar_cierra_sesiones_abiertas(self):
        login = self.login(CLAVE)
        self.temporal()
        res = self.client.post(reverse("token-refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_si_el_correo_falla_la_respuesta_no_cambia(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("sin red")):
            res = self.solicitar()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Notificacion.objects.get().estado_correo, Notificacion.EstadoCorreo.ERROR)


# ---------------------------------------------------------------------------
# Cambio desde el Perfil
# ---------------------------------------------------------------------------
class CambioDesdePerfilTests(Base):
    def setUp(self):
        super().setUp()
        self.sesion = self.login(CLAVE).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.sesion['access']}")

    def pedir(self):
        return self.post(reverse("clave-temporal"))

    def cambiar(self, temporal, nueva=NUEVA):
        return self.post(reverse("change-password"), {"clave_temporal": temporal, "new_password": nueva})

    def test_flujo_completo(self):
        res = self.pedir()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("ana@edugest.test", res.data["detail"])
        [correo] = mail.outbox
        self.assertIn("clave temporal", correo.subject)
        temporal = temporal_del_correo(correo)

        # Pedir la clave NO cambia la contraseña actual.
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CLAVE))
        self.assertFalse(self.user.must_change_password)
        self.assertNotIn(temporal, CodigoRecuperacion.objects.get().codigo_hash)
        self.assertFalse(Notificacion.objects.filter(mensaje__contains=temporal).exists())

        res = self.cambiar(temporal)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("actualizó", mail.outbox[-1].subject)
        self.assertEqual(self.login(NUEVA).status_code, 200)
        self.assertNotEqual(self.login(CLAVE).status_code, 200)
        self.assertNotEqual(self.login(temporal).status_code, 200)  # nunca fue una contraseña de ingreso

        # La sesión anterior se cerró; con los tokens nuevos sigue operando.
        res2 = self.client.post(reverse("token-refresh"), {"refresh": self.sesion["refresh"]}, format="json")
        self.assertEqual(res2.status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.cambiar(temporal, "OtraClave2026!!").status_code, 400)  # un solo uso

    def test_sin_pedir_la_clave_no_se_puede_cambiar(self):
        res = self.cambiar(CLAVE)
        self.assertIn("Primero solicita una clave temporal", str(res.data["clave_temporal"]))

    def test_intentos_y_vencimiento(self):
        self.pedir()
        temporal = temporal_del_correo(mail.outbox[0])
        for restantes in (4, 3, 2, 1):
            self.assertIn(f"Te quedan {restantes}", str(self.cambiar("ClaveIncorrecta1").data["clave_temporal"]))
        self.assertIn("agotaron", str(self.cambiar("ClaveIncorrecta1").data["clave_temporal"]))
        self.assertEqual(self.cambiar(temporal).status_code, 400)  # anulada

        with override_settings(RECUPERACION_ESPERA_SEGUNDOS=0):
            cache.delete(f"perfil:espera:{self.user.pk}")
            self.pedir()
        temporal = temporal_del_correo(mail.outbox[-1])
        CodigoRecuperacion.objects.filter(tipo="CAMBIO_CLAVE", usado_en__isnull=True).update(
            expira_en=timezone.now() - timedelta(seconds=1)
        )
        self.assertIn("venció", str(self.cambiar(temporal).data["clave_temporal"]))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(CLAVE))

    def test_clave_nueva_invalida_no_gasta_intentos(self):
        self.pedir()
        temporal = temporal_del_correo(mail.outbox[0])
        self.assertIn("new_password", self.cambiar(temporal, CLAVE).data)  # igual a la actual
        self.assertIn("new_password", self.cambiar(temporal, "12345678").data)  # débil
        self.assertEqual(CodigoRecuperacion.objects.get().intentos, 0)
        self.assertEqual(self.cambiar(temporal).status_code, 200)

    @override_settings(RECUPERACION_ESPERA_SEGUNDOS=0)
    def test_una_clave_nueva_anula_la_anterior(self):
        self.pedir()
        primera = temporal_del_correo(mail.outbox[0])
        self.pedir()
        segunda = temporal_del_correo(mail.outbox[1])
        self.assertEqual(self.cambiar(primera).status_code, 400)
        self.assertEqual(self.cambiar(segunda).status_code, 200)

    def test_espera_entre_solicitudes(self):
        self.assertEqual(self.pedir().status_code, 200)
        self.assertEqual(self.pedir().status_code, 429)

    def test_el_codigo_de_recuperacion_no_sirve_en_el_perfil(self):
        self.client.credentials()
        self.post(reverse("recuperar-solicitar"), {"email": "ana@edugest.test"})
        codigo = codigo_del_correo(mail.outbox[0])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.sesion['access']}")
        self.assertEqual(self.cambiar(codigo).status_code, 400)

    def test_requiere_sesion(self):
        self.client.credentials()
        self.assertEqual(self.client.post(reverse("clave-temporal")).status_code, 401)

    def test_con_clave_temporal_pendiente_no_pide_otra(self):
        self.user.must_change_password = True
        self.user.save()
        self.assertEqual(self.pedir().status_code, 400)


# ---------------------------------------------------------------------------
# Administración de cuentas
# ---------------------------------------------------------------------------
class AdminCuentasTests(Base):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("admin@edugest.test", "ClaveAdmin123", first_name="Admin",
                                              last_name="Uno", role=Role.ADMINISTRADOR, must_change_password=False)
        self.client.force_authenticate(self.admin)

    def crear(self, email="nuevo@edugest.test", role=Role.REPRESENTANTE):
        return self.post(reverse("user-list"), {"email": email, "first_name": "Luis", "last_name": "Vera", "role": role})

    def test_bienvenida_solo_por_correo(self):
        res = self.crear()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotIn("temporary_password", res.data)
        [correo] = mail.outbox
        self.assertEqual(correo.to, ["nuevo@edugest.test"])
        self.assertIn("representado", correo.body)
        temporal = temporal_del_correo(correo)
        self.assertEqual(self.login(temporal, "nuevo@edugest.test").status_code, 200)

    def test_reenviar_acceso_a_cuenta_sin_activar(self):
        self.crear()
        anterior = temporal_del_correo(mail.outbox[0])
        nuevo = User.objects.get(email="nuevo@edugest.test")
        res = self.post(reverse("user-reenviar-acceso", args=[nuevo.id]))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn("temporary_password", res.data)
        self.assertIn("nuevo@edugest.test", res.data["detail"])
        nueva = temporal_del_correo(mail.outbox[1])
        self.assertIn("Nuevo acceso", mail.outbox[1].subject)
        self.assertNotEqual(self.login(anterior, "nuevo@edugest.test").status_code, 200)
        self.assertEqual(self.login(nueva, "nuevo@edugest.test").status_code, 200)

    def test_no_reenvia_a_cuentas_ya_activadas_ni_inactivas(self):
        self.login(CLAVE)  # Ana ya ingresó alguna vez
        res = self.post(reverse("user-reenviar-acceso", args=[self.user.id]))
        self.assertEqual(res.status_code, 400)
        self.assertIn("¿Olvidaste tu contraseña?", res.data["detail"])

        self.crear()
        nuevo = User.objects.get(email="nuevo@edugest.test")
        nuevo.is_active = False
        nuevo.save()
        self.assertEqual(self.post(reverse("user-reenviar-acceso", args=[nuevo.id])).status_code, 400)

    def test_solo_el_admin_reenvia(self):
        self.crear()
        nuevo = User.objects.get(email="nuevo@edugest.test")
        self.client.force_authenticate(self.user)
        self.assertEqual(self.post(reverse("user-reenviar-acceso", args=[nuevo.id])).status_code, 403)

    def test_estado_del_correo_de_acceso_en_la_lista(self):
        self.crear()
        datos = {u["email"]: u for u in self.client.get(reverse("user-list")).data["results"]}
        self.assertEqual((datos["nuevo@edugest.test"]["acceso_pendiente"], datos["nuevo@edugest.test"]["correo_acceso"]),
                         (True, "ENVIADO"))
        self.assertEqual((datos["ana@edugest.test"]["acceso_pendiente"], datos["ana@edugest.test"]["correo_acceso"]),
                         (False, None))

    @override_settings(EMAIL_BACKEND="apps.notifications.backends.ResendEmailBackend", RESEND_API_KEY="re_prueba")
    def test_backend_resend(self):
        with mock.patch("apps.notifications.backends.requests.post") as post:
            post.return_value.status_code = 200
            self.crear("x@edugest.test", Role.DOCENTE)
        cuerpo = post.call_args.kwargs["json"]
        self.assertEqual(cuerpo["to"], ["x@edugest.test"])
        self.assertIn("<html", cuerpo["html"])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer re_prueba")


class CorreoDeAccesoFallidoTests(APITransactionTestCase):
    """
    Con transacciones reales (como en producción) el correo sale antes de responder, así que
    el admin ve en la misma respuesta si el correo de acceso falló.
    """

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@edugest.test", "ClaveAdmin123", first_name="Admin",
                                              last_name="Uno", role=Role.ADMINISTRADOR, must_change_password=False)
        self.client.force_authenticate(self.admin)

    def post(self, url, data=None):
        return self.client.post(url, data or {}, format="json")

    def crear(self, email, role):
        return self.post(reverse("user-list"), {"email": email, "first_name": "Luis", "last_name": "Vera", "role": role})

    @override_settings(EMAIL_BACKEND="apps.notifications.backends.ResendEmailBackend", RESEND_API_KEY="re_prueba")
    def test_si_el_correo_falla_el_admin_lo_ve_y_puede_reenviar(self):
        with mock.patch("apps.notifications.backends.requests.post") as post:
            post.return_value.status_code = 403
            post.return_value.json.return_value = {"message": "You can only send testing emails to your own email address"}
            res = self.crear("x@edugest.test", Role.DOCENTE)
            self.assertEqual(res.status_code, 201)  # el alta no falla por el correo
            self.assertEqual(res.data["correo_acceso"], "ERROR")
            n = Notificacion.objects.get(tipo="cuenta_creada")
            self.assertIn("own email address", n.error_correo)

            nuevo = User.objects.get(email="x@edugest.test")
            with self.assertLogs("django.request", level="ERROR"):
                res = self.post(reverse("user-reenviar-acceso", args=[nuevo.id]))
            self.assertEqual(res.status_code, 502)
            self.assertIn("No se pudo enviar", res.data["detail"])

            post.return_value.status_code = 200
            res = self.post(reverse("user-reenviar-acceso", args=[nuevo.id]))
            self.assertEqual((res.status_code, res.data["correo_acceso"]), (200, "ENVIADO"))


# ---------------------------------------------------------------------------
# Vencimiento de la contraseña temporal de bienvenida (2 horas)
# ---------------------------------------------------------------------------
class VencimientoBienvenidaTests(Base):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("admin@edugest.test", "ClaveAdmin123", first_name="Admin",
                                              last_name="Uno", role=Role.ADMINISTRADOR, must_change_password=False)
        self.client.force_authenticate(self.admin)
        self.post(reverse("user-list"), {"email": "nuevo@edugest.test", "first_name": "Luis",
                                         "last_name": "Vera", "role": Role.REPRESENTANTE})
        self.client.force_authenticate(None)
        self.nuevo = User.objects.get(email="nuevo@edugest.test")
        self.temporal = temporal_del_correo(mail.outbox[-1])

    def vencer(self):
        User.objects.filter(pk=self.nuevo.pk).update(clave_temporal_expira_en=timezone.now() - timedelta(minutes=1))

    def entrar(self, clave):
        with self.captureOnCommitCallbacks(execute=True):
            return self.login(clave, "nuevo@edugest.test")

    def test_vence_en_2_horas_y_el_correo_lo_indica(self):
        restante = self.nuevo.clave_temporal_expira_en - timezone.now()
        self.assertTrue(timedelta(hours=1, minutes=59) < restante <= timedelta(hours=2))
        self.assertIn("vence el", mail.outbox[-1].body)
        self.assertEqual(self.entrar(self.temporal).status_code, 200)  # dentro del plazo

    def test_al_vencer_se_envia_otra_y_asi_sucesivamente(self):
        anteriores = [self.temporal]
        for vuelta in range(1, 4):
            self.vencer()
            enviados = len(mail.outbox)
            res = self.entrar(anteriores[-1])
            self.assertEqual(res.status_code, 401)
            self.assertEqual(res.data["code"], "clave_temporal_vencida")
            self.assertIn("nuevo@edugest.test", res.data["detail"])
            self.assertEqual(len(mail.outbox), enviados + 1)
            correo = mail.outbox[-1]
            self.assertIn("nueva contraseña temporal", correo.subject)
            self.assertIn("venció", correo.body)
            nueva = temporal_del_correo(correo)
            self.assertNotIn(nueva, anteriores)
            anteriores.append(nueva)
            self.nuevo.refresh_from_db()
            self.assertGreater(self.nuevo.clave_temporal_expira_en, timezone.now() + timedelta(hours=1))
        # Ninguna de las anteriores sirve; la última sí.
        cache.clear()  # reinicia el límite de intentos de login (anti fuerza bruta)
        for vieja in anteriores[:-1]:
            self.assertEqual(self.entrar(vieja).status_code, 401)
        self.assertEqual(self.entrar(anteriores[-1]).status_code, 200)
        self.assertEqual(Notificacion.objects.filter(usuario=self.nuevo, tipo="acceso_renovado").count(), 3)

    def test_clave_equivocada_no_genera_correos(self):
        self.vencer()
        enviados = len(mail.outbox)
        res = self.entrar("CualquierCosa123")
        self.assertEqual(res.status_code, 401)
        self.assertNotEqual(res.data.get("code"), "clave_temporal_vencida")
        self.assertEqual(len(mail.outbox), enviados)

    def test_al_activar_la_cuenta_ya_no_vence(self):
        sesion = self.entrar(self.temporal).data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {sesion['access']}")
        self.assertEqual(self.post(reverse("change-password"), {"clave_temporal": self.temporal, "new_password": NUEVA}).status_code, 200)
        self.nuevo.refresh_from_db()
        self.assertIsNone(self.nuevo.clave_temporal_expira_en)
        self.client.credentials()
        self.assertEqual(self.entrar(NUEVA).status_code, 200)

    def test_si_vence_con_la_sesion_abierta_tambien_se_renueva(self):
        sesion = self.entrar(self.temporal).data
        self.vencer()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {sesion['access']}")
        res = self.post(reverse("change-password"), {"clave_temporal": self.temporal, "new_password": NUEVA})
        self.assertEqual((res.status_code, res.data["code"]), (401, "clave_temporal_vencida"))
        self.assertIn("nueva contraseña temporal", mail.outbox[-1].subject)

    def test_reenviar_acceso_da_un_plazo_nuevo(self):
        self.vencer()
        self.client.force_authenticate(self.admin)
        res = self.post(reverse("user-reenviar-acceso", args=[self.nuevo.id]))
        self.assertEqual(res.status_code, 200)
        self.assertIsNotNone(res.data["clave_temporal_expira_en"])
        self.client.force_authenticate(None)
        self.assertEqual(self.entrar(temporal_del_correo(mail.outbox[-1])).status_code, 200)

    def test_la_temporal_del_recuperador_no_vence(self):
        self.post(reverse("recuperar-solicitar"), {"email": "nuevo@edugest.test"})
        res = self.post(reverse("recuperar-verificar"), {"email": "nuevo@edugest.test",
                                                        "codigo": codigo_del_correo(mail.outbox[-1])})
        self.nuevo.refresh_from_db()
        self.assertIsNone(self.nuevo.clave_temporal_expira_en)
        self.assertEqual(self.entrar(res.data["temporary_password"]).status_code, 200)

    def test_migracion_da_plazo_a_las_cuentas_pendientes(self):
        import importlib

        from django.db import connection
        from django.db.migrations.loader import MigrationLoader

        User.objects.filter(pk=self.nuevo.pk).update(clave_temporal_expira_en=None)
        estado = MigrationLoader(connection).project_state(("security", "0005_user_clave_temporal_expira_en"))
        importlib.import_module("apps.security.migrations.0005_user_clave_temporal_expira_en").plazo_para_pendientes(estado.apps, None)
        self.nuevo.refresh_from_db()
        self.assertIsNotNone(self.nuevo.clave_temporal_expira_en)
        self.assertIsNone(User.objects.get(pk=self.user.pk).clave_temporal_expira_en)  # ya activada
