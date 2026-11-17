"""Recuperación de contraseña con código OTP y correos de la cuenta."""

import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.notifications.models import Notificacion

from .models import CodigoRecuperacion, Role, User


def codigo_del_correo(correo):
    return re.search(r"\b(\d{6})\b", correo.body).group(1)


def temporal_del_correo(correo):
    return re.search(r"^\s{4}(\S{12})\s*$", correo.body, re.M).group(1)


class RecuperacionTests(APITestCase):
    def post(self, *args, **kwargs):
        # Los correos salen al confirmar la transacción (on_commit): se ejecuta aquí.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("ana@edugest.test", "ClaveSegura123", first_name="Ana",
                                             last_name="Ruiz", role=Role.DOCENTE, must_change_password=False)
        mail.outbox.clear()
        self.url_solicitar = reverse("recuperar-solicitar")
        self.url_verificar = reverse("recuperar-verificar")

    def solicitar(self, email="ana@edugest.test", ip="10.0.0.1"):
        return self.post(self.url_solicitar, {"email": email}, REMOTE_ADDR=ip, format="json")

    def verificar(self, codigo, email="ana@edugest.test"):
        return self.post(self.url_verificar, {"email": email, "codigo": codigo}, format="json")

    def test_flujo_completo(self):
        res = self.solicitar("ANA@edugest.test")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, ["ana@edugest.test"])
        self.assertIn("código", correo.subject)
        self.assertIn("text/html", correo.alternatives[0][1])
        codigo = codigo_del_correo(correo)

        # El código no se guarda en claro y el aviso en la app no lo contiene.
        registro = CodigoRecuperacion.objects.get()
        self.assertNotIn(codigo, registro.codigo_hash)
        self.assertNotIn(codigo, Notificacion.objects.get(tipo="recuperacion_codigo").mensaje)

        res = self.verificar(f"{codigo[:3]} {codigo[3:]}")  # acepta espacios
        self.assertEqual(res.status_code, 200, res.data)
        temporal = res.data["temporary_password"]
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(temporal))
        self.assertTrue(self.user.must_change_password)
        self.assertEqual(temporal_del_correo(mail.outbox[1]), temporal)  # también llega por correo
        self.assertFalse(Notificacion.objects.filter(mensaje__contains=temporal).exists())

        # Con la temporal se ingresa y se crea la nueva.
        login = self.post(reverse("login"), {"email": "ana@edugest.test", "password": temporal}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = self.post(reverse("change-password"), {"old_password": temporal, "new_password": "MiNuevaClave2026!"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("actualizó", mail.outbox[-1].subject)

        # El código ya no sirve otra vez.
        self.client.credentials()
        self.assertEqual(self.verificar(codigo).status_code, 400)

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
            res = self.verificar(incorrecto)
            self.assertIn(f"Te quedan {restantes}", str(res.data["codigo"]))
        res = self.verificar(incorrecto)
        self.assertIn("agotaron", str(res.data["codigo"]))
        self.assertEqual(self.verificar(codigo).status_code, 400)  # invalidado aunque sea el correcto
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveSegura123"))

    def test_codigo_vencido(self):
        self.solicitar()
        codigo = codigo_del_correo(mail.outbox[0])
        CodigoRecuperacion.objects.update(expira_en=timezone.now() - timedelta(seconds=1))
        res = self.verificar(codigo)
        self.assertIn("venció", str(res.data["codigo"]))

    @override_settings(RECUPERACION_ESPERA_SEGUNDOS=0)
    def test_codigo_nuevo_invalida_el_anterior(self):
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

    def test_cierra_sesiones_abiertas(self):
        login = self.post(reverse("login"), {"email": "ana@edugest.test", "password": "ClaveSegura123"}, format="json")
        self.solicitar()
        self.verificar(codigo_del_correo(mail.outbox[0]))
        res = self.post(reverse("token-refresh"), {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)

    def test_si_el_correo_falla_la_respuesta_no_cambia(self):
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("sin red")):
            res = self.solicitar()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Notificacion.objects.get().estado_correo, Notificacion.EstadoCorreo.ERROR)


class CorreosDeCuentaTests(APITestCase):
    def post(self, *args, **kwargs):
        # Los correos salen al confirmar la transacción (on_commit): se ejecuta aquí.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(*args, **kwargs)
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@edugest.test", "ClaveAdmin123", first_name="Admin",
                                              last_name="Uno", role=Role.ADMINISTRADOR, must_change_password=False)
        self.client.force_authenticate(self.admin)
        mail.outbox.clear()

    def crear(self, email="nuevo@edugest.test", rol=Role.REPRESENTANTE):
        return self.post(reverse("user-list"), {"email": email, "first_name": "Luis", "last_name": "Vera",
                                                "role": rol}, format="json")

    def test_la_temporal_solo_llega_por_correo(self):
        res = self.crear()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertNotIn("temporary_password", res.data)
        [correo] = mail.outbox
        self.assertEqual(correo.to, ["nuevo@edugest.test"])
        self.assertIn("representado", correo.body)
        temporal = temporal_del_correo(correo)
        usuario = User.objects.get(email="nuevo@edugest.test")
        self.assertTrue(usuario.check_password(temporal))
        self.assertTrue(usuario.must_change_password)
        # Solo correo: no queda aviso en la plataforma.
        self.assertFalse(Notificacion.objects.filter(usuario=usuario).exists())

    @override_settings(EMAIL_BACKEND="apps.notifications.backends.ResendEmailBackend", RESEND_API_KEY="re_prueba")
    def test_backend_resend(self):
        with mock.patch("apps.notifications.backends.requests.post") as post:
            post.return_value.status_code = 200
            self.crear("x@edugest.test", Role.DOCENTE)
        cuerpo = post.call_args.kwargs["json"]
        self.assertEqual(cuerpo["to"], ["x@edugest.test"])
        self.assertIn("<html", cuerpo["html"])
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer re_prueba")

    @override_settings(EMAIL_BACKEND="apps.notifications.backends.ResendEmailBackend", RESEND_API_KEY="re_prueba")
    def test_si_el_correo_falla_la_cuenta_no_se_crea(self):
        with mock.patch("apps.notifications.backends.requests.post") as post:
            post.return_value.status_code = 403
            post.return_value.json.return_value = {"message": "You can only send testing emails to your own email address"}
            with self.assertLogs("django.request", level="ERROR"):
                res = self.crear("x@edugest.test", Role.DOCENTE)
        self.assertEqual(res.status_code, 502)
        self.assertIn("la cuenta no se creó", str(res.data["detail"]))
        self.assertFalse(User.objects.filter(email="x@edugest.test").exists())
        # Al corregir el problema se puede volver a crear con el mismo correo.
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self.assertEqual(self.crear("x@edugest.test", Role.DOCENTE).status_code, 201)

    def test_recuperacion_sirve_si_se_pierde_el_correo_de_bienvenida(self):
        self.crear()
        mail.outbox.clear()
        self.client.force_authenticate(None)
        res = self.post(reverse("recuperar-solicitar"), {"email": "nuevo@edugest.test"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
