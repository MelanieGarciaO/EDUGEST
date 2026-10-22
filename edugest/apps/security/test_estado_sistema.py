"""Modo mantenimiento, chequeo de salud y errores de la API en JSON."""

import logging
from unittest import mock

from django.db import OperationalError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.security.models import Role, User


class EstadoSistemaTests(APITestCase):
    def setUp(self):
        # Estas pruebas provocan errores a propósito: se silencian sus logs de nivel ERROR.
        logging.disable(logging.ERROR)
        self.addCleanup(logging.disable, logging.WARNING)

    def test_health_ok(self):
        res = self.client.get(reverse("health"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

    @override_settings(MAINTENANCE_MODE=True, MAINTENANCE_UNTIL="hoy a las 18:00")
    def test_mantenimiento_corta_la_api(self):
        res = self.client.post(reverse("login"), {"email": "a@b.com", "password": "x"})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "maintenance")
        self.assertEqual(res.json()["hasta"], "hoy a las 18:00")
        self.assertIn("Retry-After", res)

    @override_settings(MAINTENANCE_MODE=True)
    def test_health_informa_el_mantenimiento(self):
        res = self.client.get(reverse("health"))
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "maintenance")

    @override_settings(MAINTENANCE_MODE=True)
    def test_mantenimiento_deja_pasar_el_preflight_de_cors(self):
        res = self.client.options(reverse("login"))
        self.assertNotEqual(res.status_code, 503)

    def test_health_sin_base_de_datos(self):
        with mock.patch("edugest.sistema.connection.cursor", side_effect=OperationalError("caída")):
            res = self.client.get(reverse("health"))
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "service_unavailable")

    def test_base_de_datos_caida_en_un_endpoint_responde_503(self):
        user = User.objects.create_user(email="u@x.com", password="Clave-segura-1", first_name="U", last_name="X", role=Role.DOCENTE)
        self.client.force_authenticate(user)
        with mock.patch("apps.security.views.MeView.get", side_effect=OperationalError("caída")):
            res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["code"], "service_unavailable")

    def test_error_no_controlado_responde_json_sin_detalles(self):
        user = User.objects.create_user(email="u@x.com", password="Clave-segura-1", first_name="U", last_name="X", role=Role.DOCENTE)
        self.client.raise_request_exception = False
        self.client.force_authenticate(user)
        with mock.patch("apps.security.views.MeView.get", side_effect=RuntimeError("secreto interno")):
            res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()["code"], "server_error")
        self.assertNotIn("secreto", res.content.decode())
        