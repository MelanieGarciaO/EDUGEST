"""Mejora 14: evidencias fotográficas del representante (almacenamiento privado)."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from .models import ActividadRefuerzo, EvidenciaActividad
from .tests import RefuerzoBase


def foto(formato="JPEG", tamano=(2400, 1200), con_gps=True):
    img = Image.new("RGB", tamano, (200, 120, 40))
    salida = BytesIO()
    if formato == "JPEG" and con_gps:
        exif = Image.Exif()
        exif[0x010F] = "MarcaCelular"  # Make
        exif[0x8825] = {1: "S", 2: (2.0, 10.0, 0.0)}  # GPSInfo
        img.save(salida, format=formato, exif=exif)
    else:
        img.save(salida, format=formato)
    return salida.getvalue()


class EvidenciaBase(RefuerzoBase):
    def setUp(self):
        super().setUp()
        plan = self.plan_con({self.fracciones: "3.5"})
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[plan["id"]]))
        self.actividad = ActividadRefuerzo.objects.filter(tema_plan__plan_id=plan["id"]).first()
        self.url = reverse("actividad-refuerzo-evidencias", args=[self.actividad.id])

    def subir(self, contenido=None, nombre="tarea.jpg", user=None, comentario="Hizo los ejercicios"):
        self.auth(user or self.rep1)
        archivo = SimpleUploadedFile(nombre, contenido or foto(), content_type="image/jpeg")
        return self.client.post(self.url, {"archivo": archivo, "comentario": comentario}, format="multipart")


class EvidenciaTests(EvidenciaBase):
    def test_representante_sube_y_se_limpia_la_imagen(self):
        res = self.subir()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data[0]["comentario"], "Hizo los ejercicios")
        ev = EvidenciaActividad.objects.get()
        with ev.archivo.open("rb") as f, Image.open(f) as img:
            self.assertEqual(img.format, "JPEG")
            self.assertLessEqual(max(img.size), 1600)       # reducida
            self.assertNotIn(0x8825, img.getexif())          # sin GPS
            self.assertNotIn(0x010F, img.getexif())          # sin marca del celular
        self.assertTrue(ev.archivo.name.startswith(f"plan-{self.actividad.tema_plan.plan_id}/"))

    def test_png_y_webp_se_aceptan(self):
        self.assertEqual(self.subir(foto("PNG", (300, 300)), "a.png").status_code, 201)
        self.assertEqual(self.subir(foto("WEBP", (300, 300)), "a.webp").status_code, 201)

    def test_archivo_que_no_es_imagen(self):
        res = self.subir(b"%PDF-1.4 no es una foto", "tarea.jpg")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(EvidenciaActividad.objects.exists())

    @override_settings(EVIDENCIA_MAX_MB=0)
    def test_tamano_maximo(self):
        self.assertEqual(self.subir().status_code, 400)

    @override_settings(EVIDENCIAS_POR_ACTIVIDAD=2)
    def test_limite_por_actividad(self):
        self.subir()
        self.subir()
        self.assertEqual(self.subir().status_code, 400)

    def test_solo_el_representante_del_estudiante_sube(self):
        self.assertEqual(self.subir(user=self.rep2).status_code, 404)   # no ve el plan
        self.assertEqual(self.subir(user=self.doc1).status_code, 403)   # el docente solo mira

    def test_docente_y_representante_ven_la_foto_otros_no(self):
        self.subir()
        ev = EvidenciaActividad.objects.get()
        url = reverse("evidencia-archivo", args=[ev.id])
        for user, esperado in ((self.rep1, 200), (self.doc1, 200), (self.rep2, 404), (self.doc2, 404)):
            self.auth(user)
            res = self.client.get(url)
            self.assertEqual(res.status_code, esperado, user)
            if esperado == 200:
                self.assertEqual(res["Content-Type"], "image/jpeg")
                self.assertIn("private", res["Cache-Control"])
        self.auth(self.doc1)
        datos = self.client.get(self.url).data
        self.assertEqual(datos[0]["subida_por_nombre"], self.rep1.full_name)

    def test_aparece_en_el_detalle_del_plan(self):
        self.subir()
        self.auth(self.doc1)
        plan = self.client.get(reverse("plan-detail", args=[self.actividad.tema_plan.plan_id])).data
        actividades = [a for t in plan["temas"] for a in t["actividades"]]
        self.assertEqual(sum(len(a["evidencias"]) for a in actividades), 1)

    def test_eliminar_solo_quien_la_subio(self):
        self.subir()
        ev = EvidenciaActividad.objects.get()
        nombre, almacen = ev.archivo.name, ev.archivo.storage
        url = reverse("evidencia-detail", args=[ev.id])
        self.auth(self.doc1)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.auth(self.rep1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(EvidenciaActividad.objects.exists())
        self.assertFalse(almacen.exists(nombre))


# Cabeceras reales de cada formato, rellenadas hasta un tamaño razonable.
AUDIOS = {
    "webm": (b"\x1aE\xdf\xa3" + b"\x00" * 2000, "audio/webm"),
    "ogg": (b"OggS" + b"\x00" * 2000, "audio/ogg"),
    "m4a": (b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 2000, "audio/mp4"),
    "mp3": (b"ID3\x03\x00" + b"\x00" * 2000, "audio/mpeg"),
    "wav": (b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 2000, "audio/wav"),
}


class EvidenciaAudioTextoTests(EvidenciaBase):
    """DUA · acción y expresión: además de foto, el estudiante puede explicar con audio o texto."""

    def subir_audio(self, contenido, nombre="explicacion.webm", user=None):
        self.auth(user or self.rep1)
        archivo = SimpleUploadedFile(nombre, contenido, content_type="audio/webm")
        return self.client.post(self.url, {"tipo": "AUDIO", "archivo": archivo}, format="multipart")

    def subir_texto(self, texto, user=None):
        self.auth(user or self.rep1)
        return self.client.post(self.url, {"tipo": "TEXTO", "texto": texto, "comentario": "Lo escribió él"})

    def test_audio_en_varios_formatos_se_guarda_y_se_entrega_con_su_tipo(self):
        for extension, (contenido, content_type) in AUDIOS.items():
            res = self.subir_audio(contenido, f"voz.{extension}")
            self.assertEqual(res.status_code, 201, (extension, res.data))
            ev = EvidenciaActividad.objects.order_by("-id").first()
            self.assertEqual((ev.tipo, ev.tipo_contenido), ("AUDIO", content_type))
            self.assertTrue(ev.archivo.name.endswith("." + ("m4a" if extension == "m4a" else extension)))
            self.auth(self.doc1)
            entrega = self.client.get(reverse("evidencia-archivo", args=[ev.id]))
            self.assertEqual((entrega.status_code, entrega["Content-Type"]), (200, content_type))
            ev.delete()

    def test_audio_se_valida_por_contenido_no_por_nombre(self):
        res = self.subir_audio(b"MZ ejecutable disfrazado" + b"\x00" * 2000, "voz.mp3")
        self.assertEqual(res.status_code, 400)
        self.assertIn("audio válido", str(res.data["archivo"]))
        self.assertEqual(self.subir_audio(foto(), "voz.webm").status_code, 400)  # una foto no es audio
        self.assertFalse(EvidenciaActividad.objects.exists())

    @override_settings(EVIDENCIA_AUDIO_MAX_MB=0)
    def test_audio_tamano_maximo(self):
        self.assertEqual(self.subir_audio(AUDIOS["webm"][0]).status_code, 400)

    def test_audio_sin_archivo(self):
        self.auth(self.rep1)
        self.assertEqual(self.client.post(self.url, {"tipo": "AUDIO"}).status_code, 400)

    def test_texto(self):
        res = self.subir_texto("  Repartí la pizza en 4 partes iguales\n\ny cada parte es un cuarto.  ")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data[0]["tipo"], "TEXTO")
        self.assertEqual(res.data[0]["texto"], "Repartí la pizza en 4 partes iguales\n\ny cada parte es un cuarto.")
        ev = EvidenciaActividad.objects.get()
        self.assertFalse(ev.archivo)
        self.auth(self.doc1)
        self.assertEqual(self.client.get(reverse("evidencia-archivo", args=[ev.id])).status_code, 404)
        # Se puede eliminar aunque no tenga archivo.
        self.auth(self.rep1)
        self.assertEqual(self.client.delete(reverse("evidencia-detail", args=[ev.id])).status_code, 204)

    def test_texto_validaciones(self):
        self.assertEqual(self.subir_texto("corto").status_code, 400)
        self.assertEqual(self.subir_texto("x" * 1001).status_code, 400)
        self.auth(self.rep1)
        self.assertEqual(self.client.post(self.url, {"tipo": "VIDEO", "texto": "x" * 20}).status_code, 400)

    @override_settings(EVIDENCIAS_POR_ACTIVIDAD=3)
    def test_el_limite_cuenta_todos_los_tipos(self):
        self.subir()
        self.subir_audio(AUDIOS["ogg"][0])
        self.subir_texto("Lo explicó con sus palabras.")
        res = self.subir_texto("Una más que no cabe.")
        self.assertEqual(res.status_code, 400)
        self.assertIn("3 evidencias", str(res.data))

    def test_el_docente_no_sube_audio_ni_texto(self):
        self.assertEqual(self.subir_texto("Esto lo intenta el docente.", user=self.doc1).status_code, 403)

    def test_tipo_audio_por_cabecera(self):
        from .evidencias import tipo_audio

        self.assertEqual(tipo_audio(b"\xff\xf1\x50\x80"), ("audio/aac", "aac"))
        self.assertEqual(tipo_audio(b"\xff\xfb\x90\x64"), ("audio/mpeg", "mp3"))
        self.assertIsNone(tipo_audio(b"%PDF-1.4"))