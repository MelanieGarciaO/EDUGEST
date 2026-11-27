"""Solo Lengua y Literatura y Matemática están habilitadas; las demás pueden existir en la BD."""

from datetime import timedelta

from django.test import override_settings
from django.utils import timezone

from apps.activities.models import Actividad
from apps.grades.models import Dificultad
from apps.reinforcement.models import PlanRefuerzo

from .asignaturas import nombre_habilitado
from .models import AsignacionDocente, Asignatura, Grado, Tema
from .tests import AcademicBase

HABILITADAS = ["Lengua y Literatura", "Matemática"]


def _lista(r):
    return r.data["results"] if "results" in r.data else r.data


@override_settings(ASIGNATURAS_HABILITADAS=HABILITADAS, GRADO_MINIMO_HABILITADO=5, GRADO_MAXIMO_HABILITADO=7)
class AsignaturasHabilitadasTests(AcademicBase):
    def setUp(self):
        super().setUp()
        # Datos previos en la BD de una asignatura no habilitada.
        self.ingles = Asignatura.objects.create(nombre="Inglés")
        self.ciencias = Asignatura.objects.create(nombre="Ciencias Naturales")
        self.asig_ingles = AsignacionDocente.objects.create(
            docente=self.doc1, paralelo=self.par_b, asignatura=self.ingles
        )
        self.tema_ingles = Tema.objects.create(grado=self.grado7, asignatura=self.ingles, nombre="Colores")
        self.act_ingles = Actividad.objects.create(
            asignacion=self.asig_ingles, creada_por=self.doc1, descripcion="Vocabulario de colores",
            fecha_entrega=timezone.localdate() + timedelta(days=2),
        )

    def test_comparacion_sin_tildes_ni_mayusculas(self):
        self.assertTrue(nombre_habilitado("  MATEMATICA "))
        self.assertTrue(nombre_habilitado("lengua y literatura"))
        self.assertFalse(nombre_habilitado("Inglés"))

    def test_catalogo_solo_muestra_las_habilitadas(self):
        self.auth(self.admin)
        nombres = sorted(a["nombre"] for a in _lista(self.client.get("/api/academic/asignaturas/")))
        self.assertEqual(nombres, HABILITADAS)

    def test_no_se_crea_ni_renombra_a_una_no_habilitada(self):
        self.auth(self.admin)
        r = self.client.post("/api/academic/asignaturas/", {"nombre": "Robótica"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("solo está habilitado para Lengua y Literatura y Matemática", str(r.data["nombre"]))
        r = self.client.patch(f"/api/academic/asignaturas/{self.mate.id}/", {"nombre": "Física"})
        self.assertEqual(r.status_code, 400)

    def test_asignacion_y_tema_de_asignatura_no_habilitada_se_rechazan(self):
        self.auth(self.admin)
        r = self.client.post(
            "/api/academic/asignaciones/",
            {"docente": self.doc2.id, "paralelo": self.par_a.id, "asignatura": self.ciencias.id},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("asignatura", r.data)
        r = self.client.post(
            "/api/academic/temas/", {"grado": self.grado7.id, "asignatura": self.ciencias.id, "nombre": "Plantas"}
        )
        self.assertEqual(r.status_code, 400)

    def test_lo_de_una_asignatura_no_habilitada_no_se_ve(self):
        self.auth(self.admin)
        asignaciones = {a["asignatura_nombre"] for a in _lista(self.client.get("/api/academic/asignaciones/"))}
        self.assertNotIn("Inglés", asignaciones)
        temas = {t["nombre"] for t in _lista(self.client.get("/api/academic/temas/"))}
        self.assertNotIn("Colores", temas)
        # doc1 tiene Inglés en el paralelo B: ese paralelo, sus estudiantes y la actividad no se ven.
        self.auth(self.doc1)
        self.assertEqual(self.ids(self.client.get("/api/academic/paralelos/")), [self.par_a.id])
        self.assertEqual(self.ids(self.client.get("/api/academic/estudiantes/")), [self.est1.id])
        actividades = [a["id"] for a in _lista(self.client.get("/api/activities/actividades/"))]
        self.assertNotIn(self.act_ingles.id, actividades)

    def test_no_se_publica_en_una_asignatura_no_habilitada(self):
        self.auth(self.doc1)
        r = self.client.post("/api/activities/actividades/", {
            "paralelo": self.par_b.id, "asignatura": self.ingles.id, "descripcion": "Leer la página 4",
            "fecha_entrega": str(timezone.localdate() + timedelta(days=3)),
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_dificultades_y_planes_de_otra_asignatura_no_se_ven(self):
        Dificultad.objects.create(estudiante=self.est2, tema=self.tema_ingles, promedio=3, nivel="ALTA", num_calificaciones=1)
        PlanRefuerzo.objects.create(estudiante=self.est2, asignatura=self.ingles, docente=self.doc1, nivel="ALTO")
        self.auth(self.admin)
        self.assertEqual(_lista(self.client.get("/api/grades/dificultades/")), [])
        self.assertEqual(_lista(self.client.get("/api/reinforcement/planes/")), [])

    @override_settings(ASIGNATURAS_HABILITADAS=[])
    def test_lista_vacia_habilita_todas(self):
        self.auth(self.admin)
        self.assertEqual(len(_lista(self.client.get("/api/academic/asignaturas/"))), 4)
        r = self.client.post("/api/academic/asignaturas/", {"nombre": "Robótica"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_grado_y_asignatura_juntos(self):
        # Una asignatura habilitada sigue respetando el rango de grados.
        g8 = Grado.objects.create(nombre="Octavo EGB", orden=8)
        self.auth(self.admin)
        r = self.client.post("/api/academic/temas/", {"grado": g8.id, "asignatura": self.mate.id, "nombre": "Álgebra"})
        self.assertEqual(r.status_code, 400)
