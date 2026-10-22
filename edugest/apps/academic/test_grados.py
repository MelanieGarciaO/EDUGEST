from django.test import override_settings
from rest_framework.test import APITestCase

from apps.security.models import Role

from .models import Asignatura, Grado, Paralelo
from .tests import AcademicBase, make_user


@override_settings(GRADO_MAXIMO_HABILITADO=4)
class GradosHabilitadosTests(AcademicBase):
    def setUp(self):
        super().setUp()
        self.g3 = Grado.objects.create(nombre="Tercero EGB", orden=3)
        self.g4 = Grado.objects.create(nombre="Cuarto EGB", orden=4)
        self.g5 = Grado.objects.create(nombre="Quinto EGB", orden=5)
        self.auth(self.admin)

    def test_lista_de_grados_solo_habilitados(self):
        r = self.client.get("/api/academic/grados/")
        ordenes = sorted(g["orden"] for g in (r.data["results"] if "results" in r.data else r.data))
        self.assertEqual(ordenes, [3, 4])

    def test_paralelo_en_grado_habilitado_se_crea(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g4.id, "nombre": "a"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_paralelo_en_grado_no_habilitado_se_rechaza(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g5.id, "nombre": "A"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("grado", r.data)

    def test_tema_en_grado_no_habilitado_se_rechaza(self):
        r = self.client.post(
            "/api/academic/temas/",
            {"grado": self.g5.id, "asignatura": self.mate.id, "nombre": "Fracciones"},
        )
        self.assertEqual(r.status_code, 400)

    def test_estudiante_en_paralelo_no_habilitado_se_rechaza(self):
        par = Paralelo.objects.create(grado=self.g5, nombre="A")  # dato previo, fuera de rango
        r = self.client.post(
            "/api/academic/estudiantes/",
            {"first_name": "Ana", "last_name": "Mora", "paralelo": par.id, "representante": self.rep1.id},
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("paralelo", r.data)

    def test_asignacion_en_paralelo_no_habilitado_se_rechaza(self):
        par = Paralelo.objects.create(grado=self.g5, nombre="A")
        r = self.client.post(
            "/api/academic/asignaciones/",
            {"docente": self.doc1.id, "paralelo": par.id, "asignatura": self.lengua.id},
        )
        self.assertEqual(r.status_code, 400)

    @override_settings(GRADO_MAXIMO_HABILITADO=5)
    def test_subir_el_limite_habilita_el_grado(self):
        r = self.client.post("/api/academic/paralelos/", {"grado": self.g5.id, "nombre": "A"})
        self.assertEqual(r.status_code, 201, r.data)

    def test_se_puede_editar_un_paralelo_existente_fuera_de_rango(self):
        par = Paralelo.objects.create(grado=self.g5, nombre="B")
        r = self.client.patch(f"/api/academic/paralelos/{par.id}/", {"is_active": False})
        self.assertEqual(r.status_code, 200, r.data)
