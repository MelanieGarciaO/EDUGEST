"""Política de privacidad y términos: datos públicos y registro de la aceptación."""

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.security.models import Role, User


@override_settings(LEGAL_VERSION="2.0", INSTITUCION_NOMBRE="UE Ejemplo", INSTITUCION_CORREO_PRIVACIDAD="datos@ue.ec")
class TerminosTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="rep@x.com", password="Clave-segura-1", first_name="Ana", last_name="Ruiz",
            role=Role.REPRESENTANTE, must_change_password=False,
        )

    def test_datos_legales_son_publicos(self):
        res = self.client.get(reverse("legal"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["version"], "2.0")
        self.assertEqual(res.data["institucion"], "UE Ejemplo")
        self.assertEqual(res.data["correo_privacidad"], "datos@ue.ec")

    def test_usuario_nuevo_debe_aceptar(self):
        self.client.force_authenticate(self.user)
        self.assertTrue(self.client.get(reverse("me")).data["debe_aceptar_terminos"])

    def test_aceptar_registra_version_y_fecha(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(reverse("aceptar-terminos"), {"version": "2.0", "acepto": True})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["debe_aceptar_terminos"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.terminos_version, "2.0")
        self.assertIsNotNone(self.user.terminos_aceptados_en)

    def test_sin_marcar_aceptar_se_rechaza(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(reverse("aceptar-terminos"), {"version": "2.0", "acepto": False})
        self.assertEqual(res.status_code, 400)

    def test_version_desactualizada_se_rechaza(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(reverse("aceptar-terminos"), {"version": "1.0", "acepto": True})
        self.assertEqual(res.status_code, 400)

    def test_nueva_version_vuelve_a_pedir_aceptacion(self):
        self.user.terminos_version = "1.0"
        self.user.save()
        self.client.force_authenticate(self.user)
        self.assertTrue(self.client.get(reverse("me")).data["debe_aceptar_terminos"])

    def test_aceptar_exige_sesion(self):
        res = self.client.post(reverse("aceptar-terminos"), {"version": "2.0", "acepto": True})
        self.assertEqual(res.status_code, 401)
