from datetime import date, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.academic.models import Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo
from apps.security.models import Role, User
from apps.security.serializers import LoginSerializer

from . import selectors
from .models import Actividad, Extraccion
from .signals import actividad_cancelada, actividad_modificada, actividad_publicada

PASSWORD = "ClaveSegura2026"
HOY = date(2026, 10, 1)  # jueves
MANANA = HOY + timedelta(days=1)


def make_user(email, role, **extra):
    extra.setdefault("must_change_password", False)
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Nombre", last_name=email.split("@")[0],
        role=role, **extra,
    )


class ActivitiesBase(APITestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("django.utils.timezone.localdate", return_value=HOY)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.admin = make_user("admin@edugest.test", Role.ADMINISTRADOR)
        self.doc1 = make_user("doc1@edugest.test", Role.DOCENTE)
        self.doc2 = make_user("doc2@edugest.test", Role.DOCENTE)
        self.rep1 = make_user("rep1@edugest.test", Role.REPRESENTANTE)
        self.rep2 = make_user("rep2@edugest.test", Role.REPRESENTANTE)

        grado = Grado.objects.create(nombre="Séptimo EGB", orden=7)
        self.par_a = Paralelo.objects.create(grado=grado, nombre="A")
        self.par_b = Paralelo.objects.create(grado=grado, nombre="B")
        self.mate = Asignatura.objects.create(nombre="Matemática")
        self.lengua = Asignatura.objects.create(nombre="Lengua y Literatura")

        # doc1: Matemática en A. doc2: Lengua en B.
        self.asig1 = AsignacionDocente.objects.create(
            docente=self.doc1, paralelo=self.par_a, asignatura=self.mate
        )
        self.asig2 = AsignacionDocente.objects.create(
            docente=self.doc2, paralelo=self.par_b, asignatura=self.lengua
        )
        self.est1 = Estudiante.objects.create(
            first_name="Luis", last_name="Pérez", paralelo=self.par_a, representante=self.rep1
        )
        self.est2 = Estudiante.objects.create(
            first_name="Sofía", last_name="Mora", paralelo=self.par_b, representante=self.rep2
        )

        self.eventos = []
        self._conectar(actividad_publicada, "publicada")
        self._conectar(actividad_modificada, "modificada")
        self._conectar(actividad_cancelada, "cancelada")

    def _conectar(self, senal, nombre):
        def receptor(sender, actividad, **kwargs):
            self.eventos.append((nombre, actividad.pk, kwargs.get("campos")))

        senal.connect(receptor, weak=False)
        self.addCleanup(senal.disconnect, receptor)

    def auth(self, user):
        token = LoginSerializer.get_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def crear_actividad(self, asignacion=None, fecha=MANANA, **extra):
        asignacion = asignacion or self.asig1
        return Actividad.objects.create(
            asignacion=asignacion,
            creada_por=asignacion.docente,
            descripcion=extra.pop("descripcion", "Realizar las páginas 20 y 21"),
            fecha_entrega=fecha,
            **extra,
        )

    def payload(self, **cambios):
        datos = {
            "paralelo": self.par_a.id,
            "asignatura": self.mate.id,
            "descripcion": "Realizar las páginas 20 y 21",
            "fecha_entrega": "2026-10-05",
            "materiales": ["regla", "compás"],
        }
        datos.update(cambios)
        return datos

    @staticmethod
    def ids(response):
        return sorted(item["id"] for item in response.data["results"])


class PrevisualizarTests(ActivitiesBase):
    url = "/api/activities/actividades/previsualizar/"

    def test_devuelve_propuesta_y_guarda_la_extraccion(self):
        self.auth(self.doc1)
        res = self.client.post(
            self.url,
            {
                "paralelo": self.par_a.id,
                "texto": "Para el próximo lunes realizar las páginas 20 y 21 de Matemáticas "
                "y traer regla, compás y cartulina",
            },
        )
        self.assertEqual(res.status_code, 200)
        propuesta = res.data["propuesta"]
        self.assertEqual(propuesta["asignatura"], self.mate.id)
        self.assertEqual(propuesta["fecha_entrega"], "2026-10-05")
        self.assertEqual(propuesta["materiales"], ["regla", "compás", "cartulina"])
        self.assertEqual(propuesta["descripcion"], "Realizar las páginas 20 y 21")
        self.assertEqual(
            res.data["asignaturas_disponibles"], [{"id": self.mate.id, "nombre": "Matemática"}]
        )

        extraccion = Extraccion.objects.get(pk=res.data["extraccion"])
        self.assertEqual(extraccion.docente, self.doc1)
        self.assertEqual(extraccion.resultado["fecha_entrega"], "2026-10-05")
        self.assertFalse(Actividad.objects.exists())  # La vista previa no crea actividades.

    def test_no_infiere_asignaturas_que_el_docente_no_imparte(self):
        self.auth(self.doc1)
        res = self.client.post(
            self.url, {"paralelo": self.par_a.id, "texto": "Tarea de Lengua para mañana"}
        )
        self.assertEqual(res.status_code, 200)
        # La única asignatura de doc1 en A es Matemática: se infiere con aviso.
        self.assertEqual(res.data["propuesta"]["asignatura"], self.mate.id)
        self.assertEqual(res.data["propuesta"]["confianza"]["asignatura"], "media")

    def test_paralelo_ajeno(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, {"paralelo": self.par_b.id, "texto": "Tarea para mañana"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("paralelo", res.data)

    def test_texto_vacio(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, {"paralelo": self.par_a.id, "texto": "  "})
        self.assertEqual(res.status_code, 400)

    def test_solo_docentes(self):
        datos = {"paralelo": self.par_a.id, "texto": "Tarea para mañana"}
        self.assertEqual(self.client.post(self.url, datos).status_code, 401)
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.client.post(self.url, datos).status_code, 403)


class PublicarTests(ActivitiesBase):
    url = "/api/activities/actividades/"

    def test_publicar_desde_una_extraccion(self):
        self.auth(self.doc1)
        vista = self.client.post(
            self.url + "previsualizar/",
            {"paralelo": self.par_a.id, "texto": "Realizar las páginas 20 y 21 para el lunes"},
        )
        datos = self.payload(extraccion=vista.data["extraccion"])
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url, datos)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["estado"], "PUBLICADA")
        self.assertEqual(res.data["vigencia"], "pendiente")
        self.assertEqual(res.data["docente"], self.doc1.id)
        self.assertNotIn("texto_original", res.data)

        actividad = Actividad.objects.get(pk=res.data["id"])
        self.assertEqual(actividad.creada_por, self.doc1)
        self.assertEqual(actividad.extraccion_id, vista.data["extraccion"])
        self.assertIn("lunes", actividad.texto_original)
        self.assertEqual(self.eventos, [("publicada", actividad.pk, None)])

    def test_publicar_manualmente_sin_extraccion(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload())
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(Actividad.objects.get(pk=res.data["id"]).extraccion)

    def test_fecha_de_hoy_es_valida(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(fecha_entrega="2026-10-01"))
        self.assertEqual(res.status_code, 201)

    def test_fecha_pasada(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(fecha_entrega="2026-09-30"))
        self.assertEqual(res.status_code, 400)
        self.assertIn("fecha_entrega", res.data)

    def test_asignatura_que_no_imparte_en_ese_paralelo(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(asignatura=self.lengua.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn("asignatura", res.data)

    def test_paralelo_ajeno(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(paralelo=self.par_b.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn("paralelo", res.data)

    def test_asignacion_inactiva_no_permite_publicar(self):
        self.asig1.is_active = False
        self.asig1.save()
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload())
        self.assertEqual(res.status_code, 400)

    def test_descripcion_vacia(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(descripcion="   "))
        self.assertEqual(res.status_code, 400)
        self.assertIn("descripcion", res.data)

    def test_materiales_se_limpian(self):
        self.auth(self.doc1)
        res = self.client.post(
            self.url, self.payload(materiales=["  regla ", "", "Regla", "compás", "  "])
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["materiales"], ["regla", "compás"])

    def test_demasiados_materiales(self):
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(materiales=[f"m{i}" for i in range(21)]))
        self.assertEqual(res.status_code, 400)

    def test_extraccion_ya_utilizada(self):
        self.auth(self.doc1)
        vista = self.client.post(
            self.url + "previsualizar/", {"paralelo": self.par_a.id, "texto": "Tarea para mañana"}
        )
        datos = self.payload(extraccion=vista.data["extraccion"])
        self.assertEqual(self.client.post(self.url, datos).status_code, 201)
        self.assertEqual(self.client.post(self.url, datos).status_code, 400)

    def test_extraccion_de_otro_docente(self):
        extraccion = Extraccion.objects.create(
            docente=self.doc2, paralelo=self.par_b, texto_original="x", resultado={}, motor="reglas"
        )
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(extraccion=extraccion.id))
        self.assertEqual(res.status_code, 400)
        self.assertIn("extraccion", res.data)

    def test_extraccion_de_otro_paralelo(self):
        otro = Paralelo.objects.create(grado=self.par_a.grado, nombre="C")
        AsignacionDocente.objects.create(docente=self.doc1, paralelo=otro, asignatura=self.lengua)
        extraccion = Extraccion.objects.create(
            docente=self.doc1, paralelo=otro, texto_original="x", resultado={}, motor="reglas"
        )
        self.auth(self.doc1)
        res = self.client.post(self.url, self.payload(extraccion=extraccion.id))
        self.assertEqual(res.status_code, 400)

    def test_representante_y_admin_no_publican(self):
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)


class VisibilidadTests(ActivitiesBase):
    url = "/api/activities/actividades/"

    def setUp(self):
        super().setUp()
        self.act_a = self.crear_actividad(self.asig1)
        self.act_b = self.crear_actividad(self.asig2, descripcion="Leer el capítulo 3")

    def test_docente_ve_solo_las_suyas(self):
        self.auth(self.doc1)
        self.assertEqual(self.ids(self.client.get(self.url)), [self.act_a.id])
        self.assertEqual(self.client.get(f"{self.url}{self.act_b.id}/").status_code, 404)

    def test_representante_ve_solo_las_del_paralelo_de_su_estudiante(self):
        self.auth(self.rep1)
        self.assertEqual(self.ids(self.client.get(self.url)), [self.act_a.id])
        self.assertEqual(self.client.get(f"{self.url}{self.act_b.id}/").status_code, 404)
        self.auth(self.rep2)
        self.assertEqual(self.ids(self.client.get(self.url)), [self.act_b.id])

    def test_representante_con_dos_estudiantes_ve_ambos_paralelos_sin_repetidos(self):
        Estudiante.objects.create(
            first_name="Ana", last_name="Pérez", paralelo=self.par_a, representante=self.rep1
        )
        Estudiante.objects.create(
            first_name="Leo", last_name="Pérez", paralelo=self.par_b, representante=self.rep1
        )
        self.auth(self.rep1)
        res = self.client.get(self.url)
        self.assertEqual(res.data["count"], 2)

    def test_admin_ve_todas(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(self.url).data["count"], 2)

    def test_estudiante_inactivo_deja_de_ver_actividades(self):
        self.est1.is_active = False
        self.est1.save()
        self.auth(self.rep1)
        self.assertEqual(self.client.get(self.url).data["count"], 0)

    def test_no_expone_el_texto_original_ni_la_extraccion(self):
        self.auth(self.rep1)
        item = self.client.get(self.url).data["results"][0]
        self.assertNotIn("texto_original", item)
        self.assertNotIn("extraccion", item)

    def test_requiere_autenticacion(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_clave_temporal_bloquea_la_lectura(self):
        temporal = make_user("temp@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(temporal)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_filtro_por_vigencia(self):
        vencida = self.crear_actividad(self.asig1, fecha=HOY - timedelta(days=3))
        cancelada = self.crear_actividad(self.asig1, estado=Actividad.Estado.CANCELADA)
        self.auth(self.doc1)
        pendientes = self.ids(self.client.get(self.url, {"vigencia": "pendiente"}))
        self.assertEqual(pendientes, [self.act_a.id])
        self.assertEqual(self.ids(self.client.get(self.url, {"vigencia": "finalizada"})), [vencida.id])
        self.assertEqual(self.ids(self.client.get(self.url, {"vigencia": "cancelada"})), [cancelada.id])

        vigencias = {
            i["id"]: i["vigencia"] for i in self.client.get(self.url).data["results"]
        }
        self.assertEqual(vigencias[vencida.id], "finalizada")
        self.assertEqual(vigencias[cancelada.id], "cancelada")
        self.assertEqual(vigencias[self.act_a.id], "pendiente")

    def test_vigencia_invalida(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.get(self.url, {"vigencia": "otra"}).status_code, 400)

    def test_filtro_por_estudiante(self):
        self.auth(self.rep1)
        res = self.client.get(self.url, {"estudiante": self.est1.id})
        self.assertEqual(self.ids(res), [self.act_a.id])
        # Un estudiante que no es suyo no revela nada.
        res = self.client.get(self.url, {"estudiante": self.est2.id})
        self.assertEqual(res.data["count"], 0)

    def test_filtros_por_paralelo_asignatura_y_busqueda(self):
        self.auth(self.admin)
        self.assertEqual(
            self.ids(self.client.get(self.url, {"paralelo": self.par_b.id})), [self.act_b.id]
        )
        self.assertEqual(
            self.ids(self.client.get(self.url, {"asignatura": self.mate.id})), [self.act_a.id]
        )
        self.assertEqual(
            self.ids(self.client.get(self.url, {"search": "capítulo"})), [self.act_b.id]
        )
        self.assertEqual(self.client.get(self.url, {"paralelo": "abc"}).status_code, 400)

    def test_la_actividad_cancelada_sigue_visible_para_la_familia(self):
        self.act_a.estado = Actividad.Estado.CANCELADA
        self.act_a.save()
        self.auth(self.rep1)
        res = self.client.get(self.url)
        self.assertEqual(res.data["results"][0]["vigencia"], "cancelada")


class EditarTests(ActivitiesBase):
    def setUp(self):
        super().setUp()
        self.actividad = self.crear_actividad(self.asig1, materiales=["regla"])
        self.url = f"/api/activities/actividades/{self.actividad.id}/"

    def test_editar_emite_evento_con_los_campos_cambiados(self):
        self.auth(self.doc1)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(
                self.url, {"fecha_entrega": "2026-10-08", "descripcion": "Páginas 22 y 23"}
            )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["fecha_entrega"], "2026-10-08")
        self.assertEqual(len(self.eventos), 1)
        nombre, pk, campos = self.eventos[0]
        self.assertEqual((nombre, pk), ("modificada", self.actividad.pk))
        self.assertEqual(sorted(campos), ["descripcion", "fecha_entrega"])

    def test_sin_cambios_no_emite_evento(self):
        self.auth(self.doc1)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(self.url, {"materiales": ["regla"]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.eventos, [])

    def test_no_se_puede_cambiar_asignatura_ni_paralelo(self):
        self.auth(self.doc1)
        res = self.client.patch(
            self.url, {"asignatura": self.lengua.id, "paralelo": self.par_b.id, "tema": "Fracciones"}
        )
        self.assertEqual(res.status_code, 200)
        self.actividad.refresh_from_db()
        self.assertEqual(self.actividad.asignacion, self.asig1)
        self.assertEqual(self.actividad.tema, "Fracciones")

    def test_no_se_edita_una_actividad_vencida(self):
        vencida = self.crear_actividad(self.asig1, fecha=HOY - timedelta(days=1))
        self.auth(self.doc1)
        res = self.client.patch(f"/api/activities/actividades/{vencida.id}/", {"tema": "x"})
        self.assertEqual(res.status_code, 400)

    def test_no_se_edita_una_actividad_cancelada(self):
        self.actividad.estado = Actividad.Estado.CANCELADA
        self.actividad.save()
        self.auth(self.doc1)
        self.assertEqual(self.client.patch(self.url, {"tema": "x"}).status_code, 400)

    def test_fecha_nueva_en_el_pasado(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.patch(self.url, {"fecha_entrega": "2026-09-01"}).status_code, 400)

    def test_otro_docente_no_la_encuentra(self):
        self.auth(self.doc2)
        self.assertEqual(self.client.patch(self.url, {"tema": "x"}).status_code, 404)

    def test_representante_y_admin_no_editan(self):
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.client.patch(self.url, {"tema": "x"}).status_code, 403)

    def test_no_hay_borrado_ni_put(self):
        self.auth(self.doc1)
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        self.assertEqual(self.client.put(self.url, self.payload()).status_code, 405)


class CancelarTests(ActivitiesBase):
    def setUp(self):
        super().setUp()
        self.actividad = self.crear_actividad(self.asig1)
        self.url = f"/api/activities/actividades/{self.actividad.id}/cancelar/"

    def test_cancelar_emite_evento(self):
        self.auth(self.doc1)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["estado"], "CANCELADA")
        self.assertIsNotNone(res.data["cancelada_en"])
        self.assertEqual(self.eventos, [("cancelada", self.actividad.pk, None)])

    def test_cancelar_dos_veces(self):
        self.auth(self.doc1)
        self.client.post(self.url)
        self.assertEqual(self.client.post(self.url).status_code, 400)

    def test_tambien_se_puede_cancelar_una_vencida(self):
        self.actividad.fecha_entrega = HOY - timedelta(days=2)
        self.actividad.save()
        self.auth(self.doc1)
        self.assertEqual(self.client.post(self.url).status_code, 200)

    def test_permisos(self):
        self.auth(self.doc2)
        self.assertEqual(self.client.post(self.url).status_code, 404)
        for user in (self.rep1, self.admin):
            self.auth(user)
            self.assertEqual(self.client.post(self.url).status_code, 403)


class SelectoresTests(ActivitiesBase):
    def test_representantes_de_actividad_sin_repetidos(self):
        Estudiante.objects.create(
            first_name="Ana", last_name="Pérez", paralelo=self.par_a, representante=self.rep1
        )
        actividad = self.crear_actividad(self.asig1)
        self.assertEqual(list(selectors.representantes_de_actividad(actividad)), [self.rep1])

    def test_no_incluye_representantes_inactivos_ni_de_estudiantes_inactivos(self):
        actividad = self.crear_actividad(self.asig1)
        self.est1.is_active = False
        self.est1.save()
        self.assertEqual(list(selectors.representantes_de_actividad(actividad)), [])

    def test_actividades_para_recordatorio(self):
        manana = self.crear_actividad(self.asig1, fecha=MANANA)
        self.crear_actividad(self.asig1, fecha=HOY + timedelta(days=3))
        self.crear_actividad(self.asig1, fecha=MANANA, estado=Actividad.Estado.CANCELADA)
        resultado = selectors.actividades_para_recordatorio(HOY)
        self.assertEqual([a.pk for a in resultado], [manana.pk])
    