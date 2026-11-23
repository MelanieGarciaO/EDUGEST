"""Importación y exportación de usuarios con Excel, y la cola de envío de contraseñas temporales."""

import re
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from rest_framework.test import APITestCase

from . import cola_accesos
from .models import EnvioAcceso, Role, User

CAB = ["Nombres", "Apellidos", "Correo", "Rol"]
Estado = EnvioAcceso.Estado


def xlsx(*filas):
    wb = Workbook()
    for f in filas:
        wb.active.append(f)
    salida = BytesIO()
    wb.save(salida)
    return SimpleUploadedFile("usuarios.xlsx", salida.getvalue())


def temporal_del_correo(correo):
    return re.search(r"^\s{4}(\S{12})\s*$", correo.body, re.M).group(1)


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("admin@edugest.test", "ClaveAdmin123", first_name="Admin",
                                              last_name="Uno", role=Role.ADMINISTRADOR, must_change_password=False)
        self.existente = User.objects.create_user("ya@edugest.test", "ClaveYa12345", first_name="Ya",
                                                  last_name="Existe", role=Role.DOCENTE, must_change_password=False)
        self.client.force_authenticate(self.admin)
        mail.outbox.clear()

    def subir(self, archivo, confirmar=False, user=None):
        if user:
            self.client.force_authenticate(user)
        with self.captureOnCommitCallbacks(execute=True):  # al confirmar se procesa la cola
            return self.client.post(reverse("user-importar"),
                                    {"archivo": archivo, "confirmar": "true" if confirmar else "false"},
                                    format="multipart")


class ImportarTests(Base):
    def test_vista_previa_no_guarda_ni_envia(self):
        res = self.subir(xlsx(CAB, ["Ana", "Ruiz", "Ana@Edugest.test", "Docente"]))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["total"], res.data["validas"], res.data["errores"]), (1, 1, 0))
        self.assertEqual(res.data["filas"][0]["datos"]["correo"], "ana@edugest.test")
        self.assertFalse(User.objects.filter(email="ana@edugest.test").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_cada_usuario_recibe_su_propia_clave_por_correo(self):
        res = self.subir(xlsx(
            CAB,
            ["Ana", "Ruiz", "ana@edugest.test", "Docente"],
            ["Luis", "Vera", "luis@edugest.test", "representante"],
            ["Eva", "Paz", "eva@edugest.test", "Padre de familia"],
            [None, None, None, None],
        ), confirmar=True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["creados"], res.data["correos_en_cola"]), (3, 3))
        self.assertNotIn("temporary_password", str(res.data))

        destinatarios = sorted(c.to[0] for c in mail.outbox)
        self.assertEqual(destinatarios, ["ana@edugest.test", "eva@edugest.test", "luis@edugest.test"])
        claves = {c.to[0]: temporal_del_correo(c) for c in mail.outbox}
        self.assertEqual(len(set(claves.values())), 3)  # una clave distinta por usuario
        self.assertEqual(User.objects.get(email="eva@edugest.test").role, Role.REPRESENTANTE)

        for correo, clave in claves.items():
            login = self.client.post(reverse("login"), {"email": correo, "password": clave}, format="json")
            self.assertEqual(login.status_code, 200)
            self.assertTrue(login.data["user"]["must_change_password"])
        self.assertEqual(EnvioAcceso.objects.filter(estado=Estado.ENVIADO).count(), 3)
        self.assertTrue(all(u.clave_temporal_expira_en for u in User.objects.filter(email__in=claves)))

    def test_choques_de_informacion(self):
        archivo = [
            CAB,
            ["Ana", "Ruiz", "ana@edugest.test", "Docente"],          # 2 ok
            ["Otra", "Ana", "ANA@edugest.test", "Docente"],          # 3 repetido en el archivo
            ["Ya", "Existe", "ya@edugest.test", "Docente"],          # 4 ya registrado -> omitida
            ["Leo", "Paz", "leo@edugest.test", "Director"],          # 5 rol no válido
            ["", "Gil", "gil@edugest.test", "Docente"],              # 6 sin nombres
            ["Mía", "Sol", "no-es-correo", "Docente"],               # 7 correo inválido
        ]
        res = self.subir(xlsx(*archivo))
        estados = [(f["fila"], f["estado"]) for f in res.data["filas"]]
        self.assertEqual(estados, [(2, "ok"), (3, "error"), (4, "omitida"), (5, "error"), (6, "error"), (7, "error")])
        self.assertIn("repetido en el archivo (fila 2)", res.data["filas"][1]["mensajes"][0])

        res = self.subir(xlsx(*archivo), confirmar=True)  # todo o nada
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["vista_previa"]["errores"], 4)
        self.assertFalse(User.objects.filter(email="ana@edugest.test").exists())
        self.assertFalse(EnvioAcceso.objects.exists())

    def test_nombres_con_numeros_o_simbolos(self):
        # La importación usa el mismo serializer que el formulario: misma regla de nombres.
        res = self.subir(xlsx(CAB, ["Ana2", "Ruiz", "ana@edugest.test", "Docente"],
                              ["Luis", "=HYPERLINK(1)", "luis@edugest.test", "Docente"],
                              ["José María", "Pérez-Gil", "jose@edugest.test", "Docente"]))
        self.assertEqual([f["estado"] for f in res.data["filas"]], ["error", "error", "ok"])
        self.assertIn("sin números ni símbolos", " ".join(res.data["filas"][0]["mensajes"]))

    def test_subir_el_mismo_archivo_no_duplica(self):
        archivo = (CAB, ["Ana", "Ruiz", "ana@edugest.test", "Docente"])
        self.subir(xlsx(*archivo), confirmar=True)
        res = self.subir(xlsx(*archivo), confirmar=True)
        self.assertEqual((res.data["omitidas"], res.data["creados"]), (1, 0))
        self.assertEqual(User.objects.filter(email="ana@edugest.test").count(), 1)
        self.assertEqual(EnvioAcceso.objects.count(), 1)

    def test_si_otro_admin_registro_el_correo_mientras_tanto(self):
        # 1.ª comprobación (vista previa): libre. 2.ª, ya dentro del bloqueo: otro admin lo registró.
        from . import importaciones

        with mock.patch.object(importaciones, "_correos_existentes", side_effect=[set(), {"ana@edugest.test"}]):
            res = self.subir(xlsx(CAB, ["Ana", "Ruiz", "ana@edugest.test", "Docente"],
                                  ["Luis", "Vera", "luis@edugest.test", "Docente"]), confirmar=True)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Vuelve a subir el archivo", str(res.data["archivo"]))
        self.assertFalse(User.objects.filter(email__in=["ana@edugest.test", "luis@edugest.test"]).exists())
        self.assertFalse(EnvioAcceso.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_csv_y_encabezados_alternativos(self):
        texto = "Nombre;Apellido;Email;Perfil\nMía;Luna;mia@edugest.test;Representante\n"
        res = self.subir(SimpleUploadedFile("u.csv", texto.encode("utf-8-sig")), confirmar=True)
        self.assertEqual(res.data["creados"], 1)

    def test_archivos_invalidos(self):
        self.assertEqual(self.subir(SimpleUploadedFile("a.txt", b"x")).status_code, 400)
        self.assertEqual(self.subir(xlsx(["Columna"], ["a"])).status_code, 400)
        self.assertEqual(self.subir(xlsx(CAB)).status_code, 400)

    def test_solo_administrador(self):
        archivo = xlsx(CAB, ["Ana", "Ruiz", "ana@edugest.test", "Docente"])
        self.assertEqual(self.subir(archivo, user=self.existente).status_code, 403)
        self.assertEqual(self.client.get(reverse("user-plantilla")).status_code, 403)
        self.assertEqual(self.client.get(reverse("user-exportar")).status_code, 403)

    def test_plantilla_sirve_para_importar(self):
        res = self.client.get(reverse("user-plantilla"))
        self.assertEqual(res.status_code, 200)
        wb = load_workbook(BytesIO(res.content))
        self.assertEqual(wb.sheetnames, ["Usuarios", "Instrucciones"])
        self.assertTrue(wb["Usuarios"].data_validations.dataValidation)
        wb["Usuarios"].append(["Ana", "Ruiz", "ana@edugest.test", "Docente"])
        salida = BytesIO()
        wb.save(salida)
        res = self.subir(SimpleUploadedFile("plantilla.xlsx", salida.getvalue()), confirmar=True)
        self.assertEqual(res.data["creados"], 1)


@override_settings(EMAIL_BACKEND="apps.notifications.backends.ResendEmailBackend", RESEND_API_KEY="re_prueba")
class ColaTests(Base):
    """El intermediario: ritmo, reintentos, límite del servicio y estado visible para el admin."""

    def importar(self, n=3):
        filas = [CAB] + [[f"Usuario {chr(65 + i % 26)}{chr(65 + i // 26)}", "Prueba", f"u{i}@edugest.test", "Docente"] for i in range(n)]
        with mock.patch("apps.notifications.backends.requests.post") as post:
            post.return_value.status_code = 429
            post.return_value.json.return_value = {"message": "Too many requests"}
            res = self.subir(xlsx(*filas), confirmar=True)
        return res

    def respuesta(self, codigo, mensaje="ok"):
        r = mock.Mock(status_code=codigo)
        r.json.return_value = {"message": mensaje}
        return r

    def test_limite_del_servicio_pausa_la_cola_sin_gastar_intentos(self):
        res = self.importar(3)
        self.assertEqual(res.data["creados"], 3)  # la importación no falla por el correo
        envios = list(EnvioAcceso.objects.order_by("id"))
        self.assertEqual([e.estado for e in envios], [Estado.PENDIENTE] * 3)
        self.assertEqual(envios[0].intentos, 0)
        self.assertGreater(envios[0].programado_en, timezone.now())  # reprogramado
        # Mientras está en cola, el admin lo ve así:
        datos = {u["email"]: u for u in self.client.get(reverse("user-list")).data["results"]}
        self.assertEqual(datos["u0@edugest.test"]["correo_acceso"], "EN_COLA")

        # Pasa la espera y el servicio responde: se envían todos.
        EnvioAcceso.objects.update(programado_en=timezone.now())
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(200)) as post:
            r = cola_accesos.procesar(pausa=0)
        self.assertEqual(r["ok"], 3)
        self.assertEqual(post.call_count, 3)
        self.assertEqual(EnvioAcceso.objects.filter(estado=Estado.ENVIADO).count(), 3)

    def test_reintentos_y_error_final(self):
        self.importar(1)
        envio = EnvioAcceso.objects.get()
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(422, "Invalid `to`")):
            for intento in (1, 2, 3):
                EnvioAcceso.objects.update(programado_en=timezone.now())
                cola_accesos.procesar(pausa=0)
                envio.refresh_from_db()
                self.assertEqual(envio.intentos, intento)
        self.assertEqual(envio.estado, Estado.ERROR)
        self.assertIn("Invalid", envio.ultimo_error)
        datos = {u["email"]: u for u in self.client.get(reverse("user-list")).data["results"]}
        self.assertEqual(datos["u0@edugest.test"]["correo_acceso"], "ERROR")  # «Correo no enviado»

    def test_espera_creciente_entre_reintentos(self):
        self.importar(1)
        EnvioAcceso.objects.update(programado_en=timezone.now())
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(500, "caído")):
            cola_accesos.procesar(pausa=0)
        envio = EnvioAcceso.objects.get()
        self.assertEqual((envio.estado, envio.intentos), (Estado.PENDIENTE, 1))
        self.assertGreater(envio.programado_en, timezone.now() + timedelta(seconds=50))

    def test_reenviar_a_mano_cancela_lo_que_estaba_en_cola(self):
        self.importar(1)
        usuario = User.objects.get(email="u0@edugest.test")
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(200)):
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.post(reverse("user-reenviar-acceso", args=[usuario.id]))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(EnvioAcceso.objects.get().estado, Estado.CANCELADO)

    def test_no_envia_a_cuentas_que_ya_no_estan_pendientes(self):
        self.importar(2)
        User.objects.filter(email="u0@edugest.test").update(is_active=False)
        EnvioAcceso.objects.update(programado_en=timezone.now())
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(200)) as post:
            r = cola_accesos.procesar(pausa=0)
        self.assertEqual((r["ok"], r["omitido"], post.call_count), (1, 1, 1))

    def test_libera_envios_atascados_y_comando_de_respaldo(self):
        self.importar(1)
        EnvioAcceso.objects.update(estado=Estado.ENVIANDO, tomado_en=timezone.now() - timedelta(minutes=11),
                                   programado_en=timezone.now())
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(200)):
            call_command("procesar_envios_acceso", stdout=mock.Mock())
        self.assertEqual(EnvioAcceso.objects.get().estado, Estado.ENVIADO)

    def test_un_envio_tomado_no_lo_toma_otro(self):
        self.importar(1)
        EnvioAcceso.objects.update(estado=Estado.ENVIANDO, tomado_en=timezone.now(), programado_en=timezone.now())
        with mock.patch("apps.notifications.backends.requests.post", return_value=self.respuesta(200)) as post:
            cola_accesos.procesar(pausa=0)
        self.assertEqual(post.call_count, 0)

    def test_avance_del_lote(self):
        res = self.importar(2)
        avance = self.client.get(reverse("user-cola-accesos-estado"), {"lote": res.data["lote"]}).data
        self.assertEqual((avance["PENDIENTE"], avance["ENVIADO"]), (2, 0))


class ExportarTests(Base):
    def filas(self, res):
        ws = load_workbook(BytesIO(res.content)).active
        return [list(f) for f in ws.iter_rows(min_row=7, values_only=True)]

    def test_exporta_el_listado_con_estado_de_cuenta(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("user-list"), {"email": "nuevo@edugest.test", "first_name": "Luis",
                                                    "last_name": "Vera", "role": Role.REPRESENTANTE})
        res = self.client.get(reverse("user-exportar"))
        self.assertEqual(res.status_code, 200)
        self.assertIn('filename="edugest_usuarios_', res["Content-Disposition"])
        filas = {f[3]: f for f in self.filas(res)}
        self.assertEqual(set(filas), {"admin@edugest.test", "ya@edugest.test", "nuevo@edugest.test"})
        self.assertEqual(filas["nuevo@edugest.test"][4:7], ["Representante", "Activo", "Sin activar (Correo enviado)"])
        self.assertEqual(filas["ya@edugest.test"][6], "Activa")
        self.assertNotIn("Clave", str(self.filas(res)))  # sin contraseñas

    def test_respeta_los_filtros(self):
        filas = self.filas(self.client.get(reverse("user-exportar"), {"role": Role.DOCENTE}))
        self.assertEqual([f[3] for f in filas], ["ya@edugest.test"])
        filas = self.filas(self.client.get(reverse("user-exportar"), {"search": "zzz"}))
        self.assertEqual(filas[0][0], "No hay usuarios con los filtros seleccionados.")
