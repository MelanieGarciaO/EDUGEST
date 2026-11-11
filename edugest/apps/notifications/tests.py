"""Notificaciones del negocio (app + correo), preferencias, bandeja y recordatorios."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.academic.models import Estudiante
from apps.activities.models import Actividad, ArchivoEntrega
from apps.activities.signals import actividad_cancelada, actividad_modificada, actividad_publicada
from apps.grades import services as grades_services
from apps.reinforcement.tests import RefuerzoBase

from .models import Categoria, Notificacion
from .servicio import preferencias

Estado = Notificacion.EstadoCorreo


class NotificacionesBase(RefuerzoBase):
    def setUp(self):
        super().setUp()
        Notificacion.objects.all().delete()
        mail.outbox.clear()

    def emitir(self, senal, **kwargs):
        with self.captureOnCommitCallbacks(execute=True):
            senal.send(sender=Actividad, **kwargs)

    def actividad(self, **extra):
        datos = dict(asignacion=self.asig1, creada_por=self.doc1, descripcion="Resolver la página 45 del libro",
                     fecha_entrega=timezone.localdate() + timedelta(days=1), materiales=["regla"])
        datos.update(extra)
        return Actividad.objects.create(**datos)

    def de(self, usuario, **filtros):
        return Notificacion.objects.filter(usuario=usuario, **filtros)


class ActividadesTests(NotificacionesBase):
    def test_publicada_avisa_a_los_representantes_del_paralelo(self):
        self.emitir(actividad_publicada, actividad=self.actividad())
        avisados = set(Notificacion.objects.values_list("usuario__email", flat=True))
        self.assertEqual(avisados, {"rep1@edugest.test", "rep2@edugest.test"})  # paralelo A
        self.assertEqual({c.to[0] for c in mail.outbox}, avisados)
        n = self.de(self.rep1).get()
        self.assertEqual((n.categoria, n.enlace), (Categoria.ACTIVIDADES, "/representante/actividades"))
        self.assertIn("Luis", n.mensaje)
        correo = next(c for c in mail.outbox if c.to == ["rep1@edugest.test"])
        self.assertIn("Resolver la página 45", correo.body)
        self.assertIn("http://localhost:5173/representante/actividades", correo.body)

    def test_un_aviso_por_representante_con_varios_hijos(self):
        Estudiante.objects.create(first_name="Sara", last_name="Pérez", paralelo=self.par_a, representante=self.rep1)
        self.emitir(actividad_publicada, actividad=self.actividad())
        self.assertIn("Luis y Sara", self.de(self.rep1).get().mensaje)

    def test_estudiante_inactivo_no_genera_aviso(self):
        self.est1.is_active = False
        self.est1.save()
        self.emitir(actividad_publicada, actividad=self.actividad())
        self.assertFalse(self.de(self.rep1).exists())

    def test_preferencia_desactivada(self):
        pref = preferencias(self.rep1)
        pref.actividades = False
        pref.save()
        self.emitir(actividad_publicada, actividad=self.actividad())
        self.assertEqual(self.de(self.rep1).get().estado_correo, Estado.OMITIDO)  # queda en la app
        self.assertNotIn(["rep1@edugest.test"], [c.to for c in mail.outbox])

    def test_modificada_solo_si_cambia_algo_visible(self):
        a = self.actividad()
        self.emitir(actividad_modificada, actividad=a, campos=["extraccion"])
        self.assertFalse(Notificacion.objects.exists())
        self.emitir(actividad_modificada, actividad=a, campos=["fecha_entrega", "hora_entrega"])
        self.assertIn("fecha de entrega, hora de entrega", self.de(self.rep1).get().mensaje)

    def test_cancelada(self):
        self.emitir(actividad_cancelada, actividad=self.actividad())
        self.assertTrue(self.de(self.rep1, tipo="actividad_cancelada").exists())


class CalificacionesYRefuerzoTests(NotificacionesBase):
    def test_nota_con_observacion(self):
        a = self.actividad()
        with self.captureOnCommitCallbacks(execute=True):
            grades_services.guardar_calificaciones(
                a, self.fracciones, [(self.est1.id, Decimal("6.5"), "Repasa la suma de fracciones.")], self.doc1
            )
        n = self.de(self.rep1, categoria=Categoria.CALIFICACIONES).get()
        self.assertIn("6,50", n.titulo)
        self.assertIn("Repasa la suma", n.mensaje)
        correo = next(c for c in mail.outbox if "calificación" in c.subject)
        self.assertIn("Observación del docente", correo.body)
        self.assertFalse(self.de(self.rep2, categoria=Categoria.CALIFICACIONES).exists())

    def test_plan_aprobado_y_completado(self):
        self.dar_nota(self.est1, self.fracciones, "3.5")
        plan = self.generar().data
        Notificacion.objects.all().delete()
        self.post(reverse("plan-aprobar", args=[plan["id"]]))
        n = self.de(self.rep1, tipo="plan_aprobado").get()
        self.assertEqual(n.enlace, f"/representante/planes/{plan['id']}")

        self.auth(self.rep1)
        for t in plan["temas"]:
            for act in t["actividades"]:
                self.post(reverse("actividad-refuerzo-cumplir", args=[act["id"]]))
        self.assertIn("Luis Pérez", self.de(self.doc1, tipo="plan_completado").get().titulo)

    def test_plan_cancelado_antes_de_aprobar_no_avisa(self):
        self.dar_nota(self.est1, self.fracciones, "3.5")
        plan = self.generar().data
        Notificacion.objects.all().delete()
        self.post(reverse("plan-cancelar", args=[plan["id"]]))
        self.assertFalse(self.de(self.rep1, tipo="plan_cancelado").exists())


class RecordatoriosTests(NotificacionesBase):
    def correr(self):
        salida = StringIO()
        call_command("enviar_recordatorios", stdout=salida)
        return salida.getvalue()

    def test_recuerda_entregas_de_manana_sin_repetir(self):
        self.actividad()
        self.actividad(fecha_entrega=timezone.localdate() + timedelta(days=3))  # no es mañana
        self.assertIn("Recordatorios enviados: 2", self.correr())
        self.assertEqual(self.de(self.rep1, categoria=Categoria.RECORDATORIOS).count(), 1)
        self.assertIn("Recordatorios enviados: 0", self.correr())  # no repite

    def test_omite_canceladas_y_quienes_ya_entregaron(self):
        self.actividad(estado=Actividad.Estado.CANCELADA)
        app = self.actividad(modalidad_entrega=Actividad.ModalidadEntrega.APP)
        ArchivoEntrega.objects.create(
            actividad=app, estudiante=self.est1, subido_por=self.rep1, tipo=ArchivoEntrega.Tipo.values[0],
            archivo="entregas/t.pdf", nombre="t.pdf", tamano=10,
        )
        self.correr()
        self.assertFalse(self.de(self.rep1, categoria=Categoria.RECORDATORIOS).exists())
        self.assertTrue(self.de(self.rep2, categoria=Categoria.RECORDATORIOS).exists())


class BandejaTests(NotificacionesBase):
    def test_bandeja_resumen_y_lectura(self):
        self.emitir(actividad_publicada, actividad=self.actividad())
        self.emitir(actividad_cancelada, actividad=self.actividad())
        self.auth(self.rep1)
        res = self.client.get(reverse("notificacion-list"))
        self.assertEqual(res.data["count"], 2)
        self.assertEqual(self.client.get(reverse("notificacion-resumen")).data, {"no_leidas": 2})

        n = res.data["results"][0]["id"]
        self.assertTrue(self.post(reverse("notificacion-leer", args=[n])).data["leida"])
        self.assertEqual(self.client.get(reverse("notificacion-list"), {"no_leidas": "true"}).data["count"], 1)
        self.assertEqual(self.post(reverse("notificacion-leer-todas")).data, {"marcadas": 1})

    def test_solo_ve_las_suyas(self):
        self.emitir(actividad_publicada, actividad=self.actividad())
        ajena = self.de(self.rep2).get()
        self.auth(self.rep1)
        self.assertEqual(self.post(reverse("notificacion-leer", args=[ajena.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("notificacion-list")).data["count"], 1)

    def test_preferencias_por_rol(self):
        self.auth(self.rep1)
        url = reverse("notificacion-preferencias")
        datos = self.client.get(url).data
        self.assertEqual([d["clave"] for d in datos["disponibles"]],
                         ["actividades", "calificaciones", "refuerzo", "recordatorios"])
        self.assertFalse(self.client.patch(url, {"calificaciones": False}, format="json").data["calificaciones"])
        self.auth(self.doc1)
        self.assertEqual([d["clave"] for d in self.client.get(url).data["disponibles"]], ["refuerzo"])

    def test_seguridad_no_se_puede_desactivar(self):
        self.assertTrue(preferencias(self.rep1).acepta_correo(Categoria.SEGURIDAD))
        self.auth(self.rep1)
        res = self.client.patch(reverse("notificacion-preferencias"), {"seguridad": False}, format="json")
        self.assertNotIn("seguridad", res.data)

    def test_requiere_sesion(self):
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("notificacion-list")).status_code, 401)
