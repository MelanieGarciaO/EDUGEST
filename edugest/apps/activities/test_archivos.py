"""Modalidad de entrega, PDF del docente y entregas del representante (imágenes o PDF)."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.academic.models import Estudiante, Tema
from apps.grades.models import Calificacion

from .models import Actividad, AdjuntoActividad, ArchivoEntrega
from .tests import ActivitiesBase

APP = Actividad.ModalidadEntrega.APP


def pdf(texto=b"Rubrica"):
    return b"%PDF-1.4\n1 0 obj<<>>endobj\n" + texto + b"\ntrailer<<>>\n%%EOF\n"


def foto():
    salida = BytesIO()
    exif = Image.Exif()
    exif[0x8825] = {1: "S", 2: (2.0, 10.0, 0.0)}  # GPS
    Image.new("RGB", (2000, 1000), (10, 120, 200)).save(salida, format="JPEG", exif=exif)
    return salida.getvalue()


class ArchivosBase(ActivitiesBase):
    def subir(self, url, contenido, nombre, user, **datos):
        self.auth(user)
        datos["archivo"] = SimpleUploadedFile(nombre, contenido)
        return self.client.post(url, datos, format="multipart")


class ModalidadTests(ArchivosBase):
    def test_por_defecto_es_presencial_y_se_puede_publicar_desde_la_app(self):
        self.auth(self.doc1)
        res = self.client.post(reverse("actividad-list"), self.payload(), format="json")
        self.assertEqual(res.data["modalidad_entrega"], "PRESENCIAL")
        res = self.client.post(reverse("actividad-list"), self.payload(modalidad_entrega="APP"), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["modalidad_entrega"], "APP")

    def test_no_se_vuelve_presencial_si_ya_hay_entregas(self):
        act = self.crear_actividad(modalidad_entrega=APP)
        self.subir(reverse("actividad-entregas", args=[act.id]), foto(), "t.jpg", self.rep1, estudiante=self.est1.id)
        self.auth(self.doc1)
        res = self.client.patch(reverse("actividad-detail", args=[act.id]), {"modalidad_entrega": "PRESENCIAL"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("modalidad_entrega", res.data)


class AdjuntosTests(ArchivosBase):
    def setUp(self):
        super().setUp()
        self.act = self.crear_actividad()
        self.url = reverse("actividad-adjuntos", args=[self.act.id])

    def test_docente_adjunta_pdf_y_los_representantes_lo_descargan(self):
        res = self.subir(self.url, pdf(), "Rúbrica final.pdf", self.doc1)
        self.assertEqual(res.status_code, 201, res.data)
        adjunto = res.data["adjuntos"][0]
        self.assertEqual(adjunto["nombre"], "Rubrica final.pdf")
        url = reverse("adjunto-archivo", args=[adjunto["id"]])
        for user, esperado in ((self.rep1, 200), (self.doc1, 200), (self.admin, 200), (self.rep2, 404), (self.doc2, 404)):
            self.auth(user)
            r = self.client.get(url)
            self.assertEqual(r.status_code, esperado, user)
            if esperado == 200:
                self.assertEqual(r["Content-Type"], "application/pdf")
                self.assertTrue(b"".join(r.streaming_content).startswith(b"%PDF"))

    def test_solo_pdf_validos(self):
        self.assertEqual(self.subir(self.url, b"no soy pdf", "a.pdf", self.doc1).status_code, 400)
        self.assertEqual(self.subir(self.url, b"%PDF-1.4 cortado", "a.pdf", self.doc1).status_code, 400)
        self.assertEqual(self.subir(self.url, pdf(b"/Encrypt"), "a.pdf", self.doc1).status_code, 400)
        self.assertEqual(self.subir(self.url, foto(), "a.pdf", self.doc1).status_code, 400)

    @override_settings(ADJUNTOS_POR_ACTIVIDAD=1)
    def test_limite_de_adjuntos(self):
        self.subir(self.url, pdf(), "a.pdf", self.doc1)
        self.assertEqual(self.subir(self.url, pdf(), "b.pdf", self.doc1).status_code, 400)

    def test_solo_el_docente_de_la_actividad(self):
        self.assertEqual(self.subir(self.url, pdf(), "a.pdf", self.doc2).status_code, 404)
        self.assertEqual(self.subir(self.url, pdf(), "a.pdf", self.rep1).status_code, 403)

    def test_eliminar_adjunto(self):
        res = self.subir(self.url, pdf(), "a.pdf", self.doc1)
        adj = AdjuntoActividad.objects.get()
        nombre, almacen = adj.archivo.name, adj.archivo.storage
        url = reverse("adjunto-detail", args=[res.data["adjuntos"][0]["id"]])
        self.auth(self.rep1)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.auth(self.doc1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(almacen.exists(nombre))

    def test_actividad_cancelada_no_admite_adjuntos(self):
        self.act.estado = Actividad.Estado.CANCELADA
        self.act.save()
        self.assertEqual(self.subir(self.url, pdf(), "a.pdf", self.doc1).status_code, 400)


class EntregasTests(ArchivosBase):
    def setUp(self):
        super().setUp()
        self.act = self.crear_actividad(modalidad_entrega=APP, fecha=date(2099, 1, 1))
        self.url = reverse("actividad-entregas", args=[self.act.id])

    def entregar(self, contenido=None, nombre="tarea.jpg", user=None, estudiante=None):
        return self.subir(self.url, contenido or foto(), nombre, user or self.rep1, estudiante=estudiante or self.est1.id)

    def test_representante_entrega_foto_y_pdf(self):
        res = self.entregar()
        self.assertEqual(res.status_code, 201, res.data)
        res = self.entregar(pdf(), "taller.pdf")
        fila = res.data["entregas"][0]
        self.assertEqual((fila["entregada"], fila["tardia"], fila["calificada"]), (True, False, False))
        self.assertEqual([a["tipo"] for a in fila["archivos"]], ["IMAGEN", "PDF"])
        imagen = ArchivoEntrega.objects.get(tipo="IMAGEN")
        with imagen.archivo.open("rb") as f, Image.open(f) as img:
            self.assertNotIn(0x8825, img.getexif())          # sin GPS
            self.assertLessEqual(max(img.size), 1600)

    def test_actividad_presencial_no_admite_entregas(self):
        act = self.crear_actividad()
        res = self.subir(reverse("actividad-entregas", args=[act.id]), foto(), "t.jpg", self.rep1, estudiante=self.est1.id)
        self.assertEqual(res.status_code, 400)

    def test_solo_el_representante_de_su_estudiante(self):
        self.assertEqual(self.entregar(user=self.rep2).status_code, 404)              # no ve la actividad
        otro = Estudiante.objects.create(first_name="Ana", last_name="Ríos", paralelo=self.par_a, representante=self.rep2)
        self.assertEqual(self.entregar(estudiante=otro.id).status_code, 400)         # no es su representado
        self.assertEqual(self.entregar(user=self.doc1).status_code, 403)

    def test_docente_ve_todo_el_paralelo_y_el_representante_solo_lo_suyo(self):
        otro = Estudiante.objects.create(first_name="Ana", last_name="Ríos", paralelo=self.par_a, representante=self.rep2)
        self.entregar()
        self.auth(self.doc1)
        filas = self.client.get(self.url).data["entregas"]
        self.assertEqual({f["estudiante"]: f["entregada"] for f in filas}, {self.est1.id: True, otro.id: False})
        self.auth(self.rep1)
        self.assertEqual([f["estudiante"] for f in self.client.get(self.url).data["entregas"]], [self.est1.id])

    def test_entrega_fuera_de_plazo_es_tardia(self):
        act = self.crear_actividad(modalidad_entrega=APP, fecha=date(2020, 1, 1))
        res = self.subir(reverse("actividad-entregas", args=[act.id]), foto(), "t.jpg", self.rep1, estudiante=self.est1.id)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data["entregas"][0]["tardia"])

    @override_settings(ARCHIVOS_POR_ENTREGA=1)
    def test_limite_de_archivos(self):
        self.entregar()
        self.assertEqual(self.entregar().status_code, 400)

    def test_calificada_cierra_la_entrega(self):
        self.entregar()
        tema = Tema.objects.create(nombre="Fracciones", asignatura=self.mate, grado=self.par_a.grado)
        Calificacion.objects.create(actividad=self.act, estudiante=self.est1, tema=tema, valor=Decimal("9"), registrada_por=self.doc1)
        self.assertEqual(self.entregar().status_code, 400)
        registro = ArchivoEntrega.objects.get()
        self.auth(self.rep1)
        self.assertEqual(self.client.delete(reverse("archivo-entrega-detail", args=[registro.id])).status_code, 400)

    def test_ver_y_eliminar_archivo(self):
        self.entregar(pdf(), "taller.pdf")
        registro = ArchivoEntrega.objects.get()
        url = reverse("archivo-entrega-archivo", args=[registro.id])
        for user, esperado in ((self.rep1, 200), (self.doc1, 200), (self.rep2, 404), (self.doc2, 404)):
            self.auth(user)
            self.assertEqual(self.client.get(url).status_code, esperado, user)
        self.auth(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(reverse("archivo-entrega-detail", args=[registro.id])).status_code, 204)
        self.assertFalse(ArchivoEntrega.objects.exists())

    def test_archivo_invalido(self):
        self.assertEqual(self.entregar(b"hola", "t.jpg").status_code, 400)
