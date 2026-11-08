"""Material de referencia del docente (PPTX, DOCX, PDF, TXT, imágenes) para generar con IA."""

import json
from io import BytesIO
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.activities.test_lectura_archivos import pdf_con_texto

from . import ia, materiales
from .test_ia import INSTRUCCIONES
from .tests import RefuerzoBase


def pptx(*diapositivas, notas=None):
    from pptx import Presentation

    prs = Presentation()
    for i, (titulo, cuerpo) in enumerate(diapositivas):
        d = prs.slides.add_slide(prs.slide_layouts[1])
        d.shapes.title.text = titulo
        d.placeholders[1].text = cuerpo
        if notas and i == 0:
            d.notes_slide.notes_text_frame.text = notas
    salida = BytesIO()
    prs.save(salida)
    return SimpleUploadedFile("clase.pptx", salida.getvalue())


def docx(*parrafos):
    from docx import Document

    doc = Document()
    for p in parrafos:
        doc.add_paragraph(p)
    salida = BytesIO()
    doc.save(salida)
    return SimpleUploadedFile("guia.docx", salida.getvalue())


def imagen(nombre="pizarra.png"):
    salida = BytesIO()
    Image.new("RGB", (600, 400), "white").save(salida, format="PNG")
    return SimpleUploadedFile(nombre, salida.getvalue())


def pdf_escaneado():
    salida = BytesIO()
    Image.new("RGB", (600, 800), "white").save(salida, format="PDF")
    return SimpleUploadedFile("escaneo.pdf", salida.getvalue())


def respuesta(relacionado=True):
    return json.dumps({
        "material_relacionado": relacionado,
        "recursos": [{"titulo": "Fracciones con la pizza de la clase", "instrucciones": INSTRUCCIONES,
                      "estrategia": "INDIVIDUAL", "duracion_minutos": 20}],
    })


@override_settings(GEMINI_API_KEY="clave-de-prueba")
class GenerarConMaterialTests(RefuerzoBase):
    url = reverse("recurso-generar-ia")

    def setUp(self):
        super().setUp()
        parche = mock.patch.object(ia, "_llamar_modelo", return_value=respuesta())
        self.modelo = parche.start()
        self.addCleanup(parche.stop)

    def pedir(self, *archivos, user=None, **extra):
        self.auth(user or self.doc1)
        datos = {"tema": self.fracciones.id, "nivel": "BASICO", "cantidad": 1, "materiales": list(archivos), **extra}
        return self.client.post(self.url, datos, format="multipart")

    @property
    def prompt(self):
        return self.modelo.call_args.args[1]

    @property
    def adjuntos(self):
        return self.modelo.call_args.kwargs["adjuntos"]

    def test_diapositivas_pptx(self):
        res = self.pedir(pptx(("Fracciones", "Una fracción representa partes iguales de un entero."),
                              ("Suma", "Para sumar con igual denominador se suman los numeradores."),
                              notas="Usar el ejemplo de la pizza."))
        self.assertEqual(res.status_code, 200, res.data)
        for esperado in ('<material_docente archivo="clase.pptx">', "[Diapositiva 2]", "se suman los numeradores",
                         "Notas: Usar el ejemplo de la pizza", "regla 9"):
            self.assertIn(esperado, self.prompt)
        self.assertEqual(self.adjuntos, [])
        self.assertEqual(res.data["material"], {"archivos": ["clase.pptx"], "relacionado": True})
        esquema = self.modelo.call_args.args[2]
        self.assertIn("material_relacionado", esquema["required"])

    def test_docx_y_pdf_con_texto(self):
        pdf = SimpleUploadedFile("taller.pdf", pdf_con_texto("Ejercicio 1: simplifica 4/8 y 6/12 hasta su minima expresion."))
        res = self.pedir(docx("Guía de fracciones equivalentes.", "Multiplica numerador y denominador por el mismo número."), pdf)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn("Multiplica numerador y denominador", self.prompt)
        self.assertIn("simplifica 4/8", self.prompt)
        self.assertIn("[Página 1]", self.prompt)

    def test_imagen_y_pdf_escaneado_se_envian_a_gemini(self):
        res = self.pedir(imagen(), pdf_escaneado())
        self.assertEqual(res.status_code, 200, res.data)
        tipos = [(n, m) for n, m, _ in self.adjuntos]
        self.assertEqual(tipos, [("pizarra.png", "image/jpeg"), ("escaneo.pdf", "application/pdf")])
        self.assertIn("[imagen adjunta a esta solicitud]", self.prompt)
        self.assertTrue(any("escaneado" in a for a in res.data["advertencias"]))

    def test_oculta_datos_personales(self):
        texto = ("Lista: Ana López ana.lopez@correo.com, cédula 0912345678, celular 0987654321. "
                 "Tema: el número 1 000 000 000 se lee mil millones.")
        res = self.pedir(SimpleUploadedFile("notas.txt", texto.encode()))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn("ana.lopez@correo.com", self.prompt)
        self.assertNotIn("0912345678", self.prompt)
        self.assertNotIn("0987654321", self.prompt)
        self.assertIn("1 000 000 000", self.prompt)  # los números de la clase se conservan
        self.assertTrue(any("Se ocultaron 3 posibles datos personales" in a for a in res.data["advertencias"]))

    def test_material_no_relacionado(self):
        self.modelo.return_value = respuesta(relacionado=False)
        res = self.pedir(docx("Historia del Ecuador: la Revolución Liberal de 1895 y sus protagonistas."))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data["material"]["relacionado"])
        self.assertTrue(any("no parece relacionado" in a for a in res.data["advertencias"]))

    def test_sin_material_sigue_funcionando(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, {"tema": self.fracciones.id, "nivel": "BASICO", "cantidad": 1}, format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNone(res.data["material"])
        self.assertNotIn("material_docente", self.prompt)

    def test_validaciones(self):
        casos = [
            (SimpleUploadedFile("virus.exe", b"MZ..."), "formato no admitido"),
            (SimpleUploadedFile("falso.pptx", b"no es zip"), "dañado"),
            (SimpleUploadedFile("vacio.txt", b"   "), "No se pudo obtener contenido"),
            (SimpleUploadedFile("foto.png", b"no es imagen"), "imagen válida"),
        ]
        for archivo, mensaje in casos:
            with self.subTest(archivo=archivo.name):
                res = self.pedir(archivo)
                self.assertEqual(res.status_code, 400)
                self.assertIn(mensaje, str(res.data["materiales"]))
        self.modelo.assert_not_called()

    def test_docx_falso_dentro_de_un_zip(self):
        import zipfile

        salida = BytesIO()
        with zipfile.ZipFile(salida, "w") as z:
            z.writestr("otro.txt", "hola")
        res = self.pedir(SimpleUploadedFile("guia.docx", salida.getvalue()))
        self.assertEqual(res.status_code, 400)

    @override_settings(IA_MATERIAL_MAX_ARCHIVOS=2)
    def test_maximo_de_archivos(self):
        res = self.pedir(imagen("a.png"), imagen("b.png"), imagen("c.png"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("hasta 2 archivos", str(res.data["materiales"]))

    @override_settings(IA_MATERIAL_MAX_CARACTERES=200)
    def test_recorta_material_extenso(self):
        res = self.pedir(SimpleUploadedFile("largo.txt", ("Las fracciones equivalentes. " * 100).encode()))
        self.assertEqual(res.status_code, 200, res.data)
        bloque = self.prompt.split('<material_docente archivo="largo.txt">')[1].split("</material_docente>")[0]
        self.assertLessEqual(len(bloque.strip()), 200)
        self.assertTrue(any("extenso" in a for a in res.data["advertencias"]))

    @override_settings(IA_MATERIAL_MAX_PAGINAS=2)
    def test_limite_de_diapositivas(self):
        res = self.pedir(pptx(("Uno", "Texto de la primera diapositiva"), ("Dos", "Texto de la segunda"),
                              ("Tres", "Texto de la tercera diapositiva")))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertNotIn("Texto de la tercera", self.prompt)
        self.assertTrue(any("primeras 2 diapositivas" in a for a in res.data["advertencias"]))

    def test_el_material_no_salta_las_validaciones_de_permiso(self):
        res = self.pedir(docx("Comprensión lectora: idea principal."), tema=self.comprension.id)
        self.assertEqual(res.status_code, 400)  # doc1 no imparte Lengua
        self.modelo.assert_not_called()

    def test_configuracion_expone_limites_del_material(self):
        self.auth(self.doc1)
        datos = self.client.get(reverse("recurso-ia-config")).data["material"]
        self.assertEqual((datos["max_archivos"], datos["max_mb"]), (3, 10))
        self.assertIn(".pptx", datos["extensiones"])


class AnonimizarTests(RefuerzoBase):
    def test_patrones(self):
        texto, n = materiales.anonimizar("RUC 0912345678001, +593 987654321, 3,1415926535 y 2 500 000")
        self.assertEqual(n, 2)
        self.assertIn("3,1415926535", texto)
        self.assertIn("2 500 000", texto)
