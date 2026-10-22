from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Role, User
from .serializers import LoginSerializer

PASSWORD = "ClaveSegura2026"


def make_user(email, role, **extra):
    extra.setdefault("must_change_password", False)
    return User.objects.create_user(
        email=email,
        password=PASSWORD,
        first_name="Nombre",
        last_name="Apellido",
        role=role,
        **extra,
    )


class BaseAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # Reinicia los contadores de throttling entre pruebas.
        self.admin = make_user("admin@edugest.test", Role.ADMINISTRADOR)
        self.docente = make_user("docente@edugest.test", Role.DOCENTE)
        self.representante = make_user("rep@edugest.test", Role.REPRESENTANTE)

    def auth(self, user):
        token = LoginSerializer.get_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
        return token


class LoginTests(BaseAPITest):
    def test_login_correcto_devuelve_tokens_y_usuario(self):
        res = self.client.post(
            reverse("login"), {"email": "docente@edugest.test", "password": PASSWORD}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["role"], Role.DOCENTE)

    def test_login_ignora_mayusculas_en_el_correo(self):
        res = self.client.post(
            reverse("login"), {"email": "DOCENTE@Edugest.test", "password": PASSWORD}
        )
        self.assertEqual(res.status_code, 200)

    def test_login_con_clave_incorrecta(self):
        res = self.client.post(
            reverse("login"), {"email": "docente@edugest.test", "password": "otra"}
        )
        self.assertEqual(res.status_code, 401)

    def test_usuario_inactivo_no_puede_ingresar(self):
        self.docente.is_active = False
        self.docente.save()
        res = self.client.post(
            reverse("login"), {"email": "docente@edugest.test", "password": PASSWORD}
        )
        self.assertEqual(res.status_code, 401)

    def test_me_exige_autenticacion(self):
        self.assertEqual(self.client.get(reverse("me")).status_code, 401)
        self.auth(self.docente)
        res = self.client.get(reverse("me"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], "docente@edugest.test")


class LogoutTests(BaseAPITest):
    def test_logout_invalida_el_refresh_token(self):
        token = LoginSerializer.get_token(self.docente)
        res = self.client.post(reverse("logout"), {"refresh": str(token)})
        self.assertEqual(res.status_code, 204)
        res = self.client.post(reverse("token-refresh"), {"refresh": str(token)})
        self.assertEqual(res.status_code, 401)

    def test_logout_con_token_basura(self):
        res = self.client.post(reverse("logout"), {"refresh": "no-es-un-token"})
        self.assertEqual(res.status_code, 400)


class RolePermissionTests(BaseAPITest):
    def test_docente_no_puede_gestionar_usuarios(self):
        self.auth(self.docente)
        self.assertEqual(self.client.get(reverse("user-list")).status_code, 403)

    def test_representante_no_puede_gestionar_usuarios(self):
        self.auth(self.representante)
        self.assertEqual(self.client.get(reverse("user-list")).status_code, 403)

    def test_administrador_lista_usuarios(self):
        self.auth(self.admin)
        res = self.client.get(reverse("user-list"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 3)

    def test_filtro_por_rol(self):
        self.auth(self.admin)
        res = self.client.get(reverse("user-list"), {"role": Role.DOCENTE})
        self.assertEqual(res.data["count"], 1)


class UserManagementTests(BaseAPITest):
    def test_admin_crea_usuario_con_clave_temporal(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("user-list"),
            {
                "email": "Nueva@Edugest.test",
                "first_name": "Ana",
                "last_name": "Torres",
                "role": Role.DOCENTE,
            },
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("temporary_password", res.data)
        self.assertTrue(res.data["must_change_password"])
        self.assertEqual(res.data["email"], "nueva@edugest.test")

        # El nuevo usuario puede ingresar, pero queda obligado a cambiar la clave.
        self.client.credentials()
        login = self.client.post(
            reverse("login"),
            {"email": "nueva@edugest.test", "password": res.data["temporary_password"]},
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data["user"]["must_change_password"])

    def test_correo_duplicado(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("user-list"),
            {
                "email": "DOCENTE@edugest.test",
                "first_name": "X",
                "last_name": "Y",
                "role": Role.DOCENTE,
            },
        )
        self.assertEqual(res.status_code, 400)

    def test_rol_invalido(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("user-list"),
            {"email": "z@edugest.test", "first_name": "X", "last_name": "Y", "role": "SUPER"},
        )
        self.assertEqual(res.status_code, 400)

    def test_desactivar_cierra_sesiones(self):
        token = LoginSerializer.get_token(self.docente)
        self.auth(self.admin)
        res = self.client.post(reverse("user-deactivate", args=[self.docente.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["is_active"])

        self.client.credentials()
        res = self.client.post(reverse("token-refresh"), {"refresh": str(token)})
        self.assertEqual(res.status_code, 401)

    def test_admin_no_puede_desactivarse_a_si_mismo(self):
        self.auth(self.admin)
        res = self.client.post(reverse("user-deactivate", args=[self.admin.pk]))
        self.assertEqual(res.status_code, 400)

    def test_admin_no_puede_quitarse_el_rol(self):
        self.auth(self.admin)
        res = self.client.patch(
            reverse("user-detail", args=[self.admin.pk]), {"role": Role.DOCENTE}
        )
        self.assertEqual(res.status_code, 400)

    def test_no_se_pueden_eliminar_usuarios(self):
        self.auth(self.admin)
        res = self.client.delete(reverse("user-detail", args=[self.docente.pk]))
        self.assertEqual(res.status_code, 405)

    def test_reset_de_contrasena(self):
        self.auth(self.admin)
        res = self.client.post(reverse("user-reset-password", args=[self.docente.pk]))
        self.assertEqual(res.status_code, 200)
        self.docente.refresh_from_db()
        self.assertTrue(self.docente.must_change_password)
        self.assertTrue(self.docente.check_password(res.data["temporary_password"]))


class PasswordChangeTests(BaseAPITest):
    def test_clave_temporal_bloquea_el_resto_de_la_api(self):
        temporal = make_user("temp@edugest.test", Role.ADMINISTRADOR, must_change_password=True)
        self.auth(temporal)
        res = self.client.get(reverse("user-list"))
        self.assertEqual(res.status_code, 403)
        # Pero puede consultar su perfil.
        self.assertEqual(self.client.get(reverse("me")).status_code, 200)

    def test_cambio_de_clave_libera_el_acceso_y_devuelve_tokens_nuevos(self):
        temporal = make_user("temp@edugest.test", Role.ADMINISTRADOR, must_change_password=True)
        viejo = self.auth(temporal)
        res = self.client.post(
            reverse("change-password"),
            {"old_password": PASSWORD, "new_password": "OtraClaveMasLarga77"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["user"]["must_change_password"])

        # El refresh anterior queda invalidado y el nuevo access ya permite operar.
        self.assertEqual(
            self.client.post(reverse("token-refresh"), {"refresh": str(viejo)}).status_code, 401
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.client.get(reverse("user-list")).status_code, 200)

    def test_clave_actual_incorrecta(self):
        self.auth(self.docente)
        res = self.client.post(
            reverse("change-password"),
            {"old_password": "mala", "new_password": "OtraClaveMasLarga77"},
        )
        self.assertEqual(res.status_code, 400)

    def test_clave_nueva_debil(self):
        self.auth(self.docente)
        res = self.client.post(
            reverse("change-password"),
            {"old_password": PASSWORD, "new_password": "12345678"},
        )
        self.assertEqual(res.status_code, 400)


class SuperuserTests(BaseAPITest):
    def test_createsuperuser_asigna_rol_administrador(self):
        su = User.objects.create_superuser(
            email="root@edugest.test", password=PASSWORD, first_name="Root", last_name="Dev"
        )
        self.assertEqual(su.role, Role.ADMINISTRADOR)
        self.assertTrue(su.is_superuser)
        self.assertFalse(su.must_change_password)
