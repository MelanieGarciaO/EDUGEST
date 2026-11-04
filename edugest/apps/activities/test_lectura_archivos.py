"""Lectura de la indicación docente desde PDF o imagen (endpoint extraer-texto)."""

from io import BytesIO
from unittest import mock, skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont

from . import lectura_archivos
from .tests import ActivitiesBase

INDICACION = "Matematica: resolver la pagina 45 del libro para el viernes. Traer regla y compas."


def pdf_con_texto(*lineas):
    """PDF digital mínimo y válido (Helvetica), una línea por renglón."""
    flujo = "BT /F1 12 Tf 50 750 Td 16 TL " + " ".join(f"({l}) '" for l in lineas) + " ET"
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(flujo)} >>\nstream\n{flujo}\nendstream",
    ]
    salida, offsets = b"%PDF-1.4\n", []
    for i, obj in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n{obj}\nendobj\n".encode()
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return salida


def imagen_con_texto(texto="Lenguaje: leer el cuento para el lunes", formato="PNG"):
    img = Image.new("RGB", (1400, 220), "white")
    fuente = ImageFont.load_default(size=44)
    ImageDraw.Draw(img).text((40, 80), texto, fill="black", font=fuente)
    salida = BytesIO()
    img.save(salida, format=formato)
    return salida.getvalue()


def pdf_escaneado():
    """PDF sin capa de texto (solo una imagen), como el de un escáner."""
    salida = BytesIO()
    Image.open(BytesIO(imagen_con_texto())).save(salida, format="PDF", resolution=150)
    return salida.getvalue()


class ExtraerTextoBase(ActivitiesBase):
    url = reverse("actividad-extraer-texto")

    def subir(self, contenido, nombre, user=None):
        self.auth(user or self.doc1)
        return self.client.post(
            self.url, {"archivo": SimpleUploadedFile(nombre, contenido)}, format="multipart"
        )


class PdfDigitalTests(ExtraerTextoBase):
    def test_extrae_el_texto_de_un_pdf_digital(self):
        res = self.subir(pdf_con_texto(INDICACION), "tarea.pdf")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["metodo"], lectura_archivos.PDF_TEXTO)
        self.assertIn("pagina 45", res.data["texto"])
        self.assertEqual(res.data["paginas"], 1)
        self.assertEqual(res.data["advertencias"], [])

    def test_el_texto_sirve_para_previsualizar(self):
        texto = self.subir(pdf_con_texto(INDICACION), "tarea.pdf").data["texto"]
        res = self.client.post(
            reverse("actividad-previsualizar"), {"paralelo": self.asig1.paralelo_id, "texto": texto}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("regla", " ".join(res.data["propuesta"]["materiales"]).lower())

    @override_settings(PLN_ARCHIVO_MAX_MB=0)
    def test_respeta_el_tamano_maximo(self):
        res = self.subir(pdf_con_texto(INDICACION), "tarea.pdf")
        self.assertEqual(res.status_code, 400)

    def test_rechaza_pdf_danado_o_protegido(self):
        self.assertEqual(self.subir(b"%PDF-1.4 cortado", "a.pdf").status_code, 400)
        self.assertEqual(self.subir(pdf_con_texto("x") + b"/Encrypt", "a.pdf").status_code, 400)

    def test_recorta_textos_largos(self):
        lineas = [INDICACION] * 40
        res = self.subir(pdf_con_texto(*lineas), "largo.pdf")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertLessEqual(len(res.data["texto"]), 2000)
        self.assertTrue(any("recortó" in a for a in res.data["advertencias"]))

    def test_solo_docentes(self):
        self.assertEqual(self.subir(pdf_con_texto(INDICACION), "t.pdf", self.rep1).status_code, 403)
        self.client.force_authenticate(None)
        res = self.client.post(self.url, {}, format="multipart")
        self.assertIn(res.status_code, (401, 403))

    def test_sin_archivo(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.post(self.url, {}, format="multipart").status_code, 400)


class OcrNoDisponibleTests(ExtraerTextoBase):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(lectura_archivos, "ocr_disponible", return_value=False)
        parche.start()
        self.addCleanup(parche.stop)

    def test_imagen_sin_ocr_da_un_error_claro(self):
        res = self.subir(imagen_con_texto(), "foto.png")
        self.assertEqual(res.status_code, 400)
        self.assertIn("no está disponible", str(res.data["archivo"]))

    def test_pdf_digital_funciona_sin_ocr(self):
        self.assertEqual(self.subir(pdf_con_texto(INDICACION), "t.pdf").status_code, 200)

    def test_archivo_que_no_es_imagen_ni_pdf(self):
        with mock.patch.object(lectura_archivos, "ocr_disponible", return_value=True):
            self.assertEqual(self.subir(b"hola", "nota.txt").status_code, 400)


class LimpiezaTests(ActivitiesBase):
    def test_une_palabras_cortadas_y_quita_ruido(self):
        texto = "Resolver la activi-\ndad   del libro\n|\n~~\n\n\n\nTraer regla"
        self.assertEqual(
            lectura_archivos.limpiar_texto(texto), "Resolver la actividad del libro\nTraer regla"
        )


@skipUnless(lectura_archivos.ocr_disponible(), "Tesseract (spa) no está instalado.")
class OcrRealTests(ExtraerTextoBase):
    def test_lee_una_imagen(self):
        res = self.subir(imagen_con_texto(formato="JPEG"), "foto.jpg")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["metodo"], lectura_archivos.IMAGEN_OCR)
        self.assertIn("cuento", res.data["texto"].lower())
        self.assertTrue(any("OCR" in a for a in res.data["advertencias"]))

    def test_lee_un_pdf_escaneado(self):
        res = self.subir(pdf_escaneado(), "escaneo.pdf")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["metodo"], lectura_archivos.PDF_OCR)
        self.assertIn("lunes", res.data["texto"].lower())

    def test_imagen_en_blanco(self):
        salida = BytesIO()
        Image.new("RGB", (800, 600), "white").save(salida, format="PNG")
        self.assertEqual(self.subir(salida.getvalue(), "vacia.png").status_code, 400)
