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


class EvidenciaTests(RefuerzoBase):
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
