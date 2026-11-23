"""
Validaciones del acceso: IP real detrás del proxy, límites del inicio de sesión (por IP y por
cuenta), longitud máxima de la contraseña y términos exigidos por la API.
"""

from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import reverse

from .models import Role
from .red import ip_cliente
from .tests import PASSWORD, BaseAPITest, make_user

PROXY = "127.0.0.1"  # así ve Django todas las peticiones detrás de Render


class IPClienteTests(BaseAPITest):
    def ip(self, remote="190.10.10.10", xff=None):
        extra = {"REMOTE_ADDR": remote}
        if xff is not None:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return ip_cliente(RequestFactory().get("/", **extra))

    @override_settings(BEHIND_PROXY=False)
    def test_sin_proxy_ignora_x_forwarded_for(self):
        self.assertEqual(self.ip(xff="1.2.3.4"), "190.10.10.10")

    @override_settings(BEHIND_PROXY=True)
    def test_con_proxy_toma_la_ultima_ip_publica(self):
        self.assertEqual(self.ip(PROXY, "181.39.1.2"), "181.39.1.2")
        # Lo que el cliente escribe a la izquierda no cuenta: el proxy agrega la real al final.
        self.assertEqual(self.ip(PROXY, "8.8.8.8, 181.39.1.2"), "181.39.1.2")
        self.assertEqual(self.ip(PROXY, "181.39.1.2, 10.0.0.5"), "181.39.1.2")
        self.assertEqual(self.ip(PROXY, "basura, 181.39.1.2"), "181.39.1.2")
        self.assertIsNone(self.ip(PROXY, ""))
        self.assertIsNone(self.ip(PROXY))


@override_settings(BEHIND_PROXY=True)
class LoginLimitesTests(BaseAPITest):
    def login(self, email, password, ip):
        return self.client.post(
            reverse("login"), {"email": email, "password": password}, format="json",
            REMOTE_ADDR=PROXY, HTTP_X_FORWARDED_FOR=ip,
        )

    def test_cambiar_x_forwarded_for_no_salta_el_limite_por_ip(self):
        estados = [self.login("admin@edugest.test", "mala", f"10.0.0.{i}, 181.39.1.2").status_code for i in range(6)]
        self.assertEqual(estados, [401] * 5 + [429])
        res = self.login("admin@edugest.test", "mala", "181.39.1.2")
        self.assertIn("Demasiados intentos. Espera", res.data["detail"])

    def test_otras_personas_no_comparten_el_limite(self):
        for _ in range(5):
            self.login("admin@edugest.test", "mala", "181.39.1.2")
        self.assertEqual(self.login("docente@edugest.test", PASSWORD, "181.39.9.9").status_code, 200)

    @override_settings(LOGIN_FALLOS_MAX=3)
    def test_bloqueo_por_cuenta_desde_varias_ips(self):
        for i in range(3):
            self.assertEqual(self.login("docente@edugest.test", "mala", f"181.39.1.{i}").status_code, 401)
        res = self.login("docente@edugest.test", PASSWORD, "181.39.2.1")  # ni con la correcta
        self.assertEqual(res.status_code, 429)
        self.assertIn("intentos fallidos con esta cuenta", res.data["detail"])
        # Otra cuenta sigue entrando; y un correo inexistente se comporta igual (no revela nada).
        self.assertEqual(self.login("admin@edugest.test", PASSWORD, "181.39.2.2").status_code, 200)
        for i in range(3):
            self.login("nadie@edugest.test", "mala", f"181.39.3.{i}")
        self.assertEqual(self.login("NADIE@edugest.test ", "mala", "181.39.3.9").status_code, 429)

    @override_settings(LOGIN_FALLOS_MAX=3)
    def test_ingreso_correcto_reinicia_el_conteo(self):
        for i in range(2):
            self.login("docente@edugest.test", "mala", f"181.39.1.{i}")
        self.assertEqual(self.login("docente@edugest.test", PASSWORD, "181.39.1.5").status_code, 200)
        for i in range(2):
            self.login("docente@edugest.test", "mala", f"181.39.4.{i}")
        self.assertEqual(self.login("docente@edugest.test", PASSWORD, "181.39.4.5").status_code, 200)

    def test_campos_vacios(self):
        res = self.login("", "", "181.39.1.2")
        self.assertEqual(res.status_code, 400)


@override_settings(BEHIND_PROXY=True, RECUPERACION_ESPERA_SEGUNDOS=0)
class RecuperacionTrasProxyTests(BaseAPITest):
    def solicitar(self, email, xff):
        extra = {"REMOTE_ADDR": PROXY}
        if xff:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return self.client.post(reverse("recuperar-solicitar"), {"email": email}, format="json", **extra)

    def test_personas_distintas_no_se_bloquean_entre_si(self):
        for i in range(8):
            usuario = make_user(f"rep{i}@edugest.test", Role.REPRESENTANTE)
            self.assertEqual(self.solicitar(usuario.email, f"181.39.5.{i}").status_code, 200, i)

    def test_limite_por_red_sigue_vigente(self):
        estados = [self.solicitar(f"x{i}@edugest.test", "8.8.8.8, 181.39.6.1").status_code for i in range(6)]
        self.assertEqual(estados, [200] * 5 + [429])

    def test_ip_desconocida_no_crea_un_limite_global(self):
        estados = [self.solicitar(f"y{i}@edugest.test", None).status_code for i in range(7)]
        self.assertEqual(estados, [200] * 7)
        # El límite por correo sí se mantiene.
        estados = [self.solicitar("z@edugest.test", None).status_code for _ in range(6)]
        self.assertEqual(estados[-1], 429)


class ClaveMaximaTests(BaseAPITest):
    def test_contrasena_nueva_maximo_128(self):
        nuevo = make_user("nuevo@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(nuevo)
        url = reverse("change-password")
        res = self.client.post(url, {"clave_temporal": PASSWORD, "new_password": "Girasol-" + "a" * 125}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("máximo 128", str(res.data["new_password"]))
        res = self.client.post(url, {"clave_temporal": PASSWORD, "new_password": "Girasol-Azul-2026"}, format="json")
        self.assertEqual(res.status_code, 200)


@override_settings(TERMINOS_OBLIGATORIOS_API=True, LEGAL_VERSION="2.0")
class TerminosEnLaAPITests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.usuario = make_user("sinterm@edugest.test", Role.DOCENTE, terminos_version="1.0")

    def test_sin_aceptar_no_usa_la_api(self):
        self.auth(self.usuario)
        res = self.client.get(reverse("actividad-list"))
        self.assertEqual((res.status_code, res.data["code"]), (403, "terminos_pendientes"))
        self.assertEqual(self.client.get(reverse("notificacion-list")).status_code, 403)
        # Lo necesario para completar el acceso sigue disponible.
        self.assertEqual(self.client.get(reverse("me")).status_code, 200)
        res = self.client.post(reverse("aceptar-terminos"), {"version": "2.0", "acepto": True}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.client.get(reverse("actividad-list")).status_code, 200)

    def test_clave_temporal_tiene_prioridad(self):
        nuevo = make_user("temp@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(nuevo)
        res = self.client.get(reverse("actividad-list"))
        self.assertEqual(res.status_code, 403)
        self.assertIn("contraseña temporal", str(res.data["detail"]))

    def tearDown(self):
        cache.clear()
        super().tearDown()
