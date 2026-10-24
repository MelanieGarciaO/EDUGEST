from django.test import override_settings
from rest_framework.test import APITestCase

from apps.security.models import Role

from .models import Asignatura, Grado, Paralelo
from .tests import AcademicBase, make_user


@override_settings(GRADO_MINIMO_HABILITADO=5, GRADO_MAXIMO_HABILITADO=7)
class GradosHabilitadosTests(AcademicBase):
    """EGB Media: solo 5.º, 6.º y 7.º están habilitados."""

    def setUp(self):
        super().setUp()
        self.g4 = Grado.objects.create(nombre="Cuarto EGB", orden=4)
        self.g6 = Grado.objects.create(nombre="Sexto EGB", orden=6)
        # Séptimo EGB (orden 7) ya lo crea AcademicBase como self.grado7.
        self.g8 = Grado.objects.create(nombre="Octavo EGB", orden=8)  # fuera de rango por arriba
        self.auth(self.admin)

    def test_lista_de_grados_solo_habilitados(self):
        r = self.client.get("/api/academic/grados/")
        ordenes = sorted(g["orden"] for g in (r.data["results"] if "results" in r.data else r.data))
        self.assertEqual(ordenes, [6, 7])

    def test_paralelo_en_grado_habilitado_se_crea(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g6.id, "nombre": "a"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_paralelo_en_grado_inferior_al_rango_se_rechaza(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g4.id, "nombre": "A"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("grado", r.data)

    def test_paralelo_en_grado_no_habilitado_se_rechaza(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g8.id, "nombre": "A"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("grado", r.data)

    def test_tema_en_grado_no_habilitado_se_rechaza(self):
        r = self.client.post(
            "/api/academic/temas/",
            {"grado": self.g8.id, "asignatura": self.mate.id, "nombre": "Fracciones"},
        )
        self.assertEqual(r.status_code, 400)

    def test_estudiante_en_paralelo_no_habilitado_se_rechaza(self):
        par = Paralelo.objects.create(grado=self.g8, nombre="A")  # dato previo, fuera de rango
        r = self.client.post(
            "/api/academic/estudiantes/",
            {"first_name": "Ana", "last_name": "Mora", "paralelo": par.id, "representante": self.rep1.id},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("paralelo", r.data)

    def test_asignacion_en_paralelo_no_habilitado_se_rechaza(self):
        par = Paralelo.objects.create(grado=self.g8, nombre="A")
        r = self.client.post(
            "/api/academic/asignaciones/",
            {"docente": self.doc1.id, "paralelo": par.id, "asignatura": self.lengua.id},
        )
        self.assertEqual(r.status_code, 400)

    @override_settings(GRADO_MINIMO_HABILITADO=5, GRADO_MAXIMO_HABILITADO=8)
    def test_subir_el_limite_habilita_el_grado(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g8.id, "nombre": "A"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_se_puede_editar_un_paralelo_existente_fuera_de_rango(self):
        par = Paralelo.objects.create(grado=self.g8, nombre="B")
        r = self.client.patch(f"/api/academic/paralelos/{par.id}/", {"is_active": False})
        self.assertEqual(r.status_code, 200, r.data)
