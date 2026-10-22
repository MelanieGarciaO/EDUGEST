from django.core.cache import cache
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.security.models import Role, User
from apps.security.serializers import LoginSerializer

from .models import Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo
from . import selectors

PASSWORD = "ClaveSegura2026"


def make_user(email, role, **extra):
    extra.setdefault("must_change_password", False)
    return User.objects.create_user(
        email=email, password=PASSWORD, first_name="Nombre", last_name=email.split("@")[0],
        role=role, **extra,
    )


class AcademicBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.admin = make_user("admin@edugest.test", Role.ADMINISTRADOR)
        self.doc1 = make_user("doc1@edugest.test", Role.DOCENTE)
        self.doc2 = make_user("doc2@edugest.test", Role.DOCENTE)
        self.rep1 = make_user("rep1@edugest.test", Role.REPRESENTANTE)
        self.rep2 = make_user("rep2@edugest.test", Role.REPRESENTANTE)

        self.grado7 = Grado.objects.create(nombre="Séptimo EGB", orden=7)
        self.par_a = Paralelo.objects.create(grado=self.grado7, nombre="A")
        self.par_b = Paralelo.objects.create(grado=self.grado7, nombre="B")
        self.mate = Asignatura.objects.create(nombre="Matemática")
        self.lengua = Asignatura.objects.create(nombre="Lengua y Literatura")

        # doc1 enseña Matemática en A; doc2 enseña Lengua en B.
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

    def auth(self, user):
        token = LoginSerializer.get_token(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    @staticmethod
    def ids(response):
        return sorted(item["id"] for item in response.data["results"])


class VisibilityTests(AcademicBase):
    def test_docente_ve_solo_sus_paralelos_estudiantes_y_asignaciones(self):
        self.auth(self.doc1)
        self.assertEqual(self.ids(self.client.get(reverse("paralelo-list"))), [self.par_a.id])
        self.assertEqual(self.ids(self.client.get(reverse("estudiante-list"))), [self.est1.id])
        self.assertEqual(self.ids(self.client.get(reverse("asignacion-list"))), [self.asig1.id])

    def test_docente_no_accede_al_detalle_de_otro_paralelo(self):
        self.auth(self.doc1)
        res = self.client.get(reverse("paralelo-detail", args=[self.par_b.id]))
        self.assertEqual(res.status_code, 404)
        res = self.client.get(reverse("estudiante-detail", args=[self.est2.id]))
        self.assertEqual(res.status_code, 404)

    def test_representante_ve_solo_a_sus_estudiantes(self):
        self.auth(self.rep1)
        self.assertEqual(self.ids(self.client.get(reverse("estudiante-list"))), [self.est1.id])
        self.assertEqual(self.ids(self.client.get(reverse("paralelo-list"))), [self.par_a.id])
        self.assertEqual(self.ids(self.client.get(reverse("asignacion-list"))), [self.asig1.id])
        res = self.client.get(reverse("estudiante-detail", args=[self.est2.id]))
        self.assertEqual(res.status_code, 404)

    def test_representante_no_ve_el_tamano_del_paralelo(self):
        self.auth(self.rep1)
        res = self.client.get(reverse("paralelo-list"))
        self.assertIsNone(res.data["results"][0]["estudiantes_count"])

    def test_representante_con_varios_estudiantes(self):
        Estudiante.objects.create(
            first_name="Ana", last_name="Pérez", paralelo=self.par_b, representante=self.rep1
        )
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("estudiante-list")).data["count"], 2)
        self.assertEqual(self.client.get(reverse("paralelo-list")).data["count"], 2)

    def test_admin_ve_todo(self):
        self.auth(self.admin)
        self.assertEqual(self.client.get(reverse("estudiante-list")).data["count"], 2)
        self.assertEqual(self.client.get(reverse("paralelo-list")).data["count"], 2)
        self.assertEqual(self.client.get(reverse("asignacion-list")).data["count"], 2)

    def test_estudiante_inactivo_deja_de_ser_visible_para_su_representante(self):
        self.est1.is_active = False
        self.est1.save()
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("paralelo-list")).data["count"], 0)

    def test_requiere_autenticacion(self):
        self.assertEqual(self.client.get(reverse("estudiante-list")).status_code, 401)

    def test_clave_temporal_bloquea_la_lectura(self):
        temporal = make_user("temp@edugest.test", Role.DOCENTE, must_change_password=True)
        self.auth(temporal)
        self.assertEqual(self.client.get(reverse("paralelo-list")).status_code, 403)

    def test_selectores_para_otros_modulos(self):
        self.assertTrue(selectors.puede_ver_estudiante(self.doc1, self.est1.id))
        self.assertFalse(selectors.puede_ver_estudiante(self.doc1, self.est2.id))
        self.assertTrue(selectors.puede_ver_estudiante(self.rep2, self.est2.id))
        self.assertTrue(selectors.docente_imparte(self.doc1, self.par_a.id, self.mate.id))
        self.assertFalse(selectors.docente_imparte(self.doc1, self.par_b.id, self.lengua.id))


class WritePermissionTests(AcademicBase):
    def test_solo_el_admin_escribe(self):
        payload = {"nombre": "Octavo EGB", "orden": 8}
        for user in (self.doc1, self.rep1):
            self.auth(user)
            self.assertEqual(self.client.post(reverse("grado-list"), payload).status_code, 403)
            self.assertEqual(
                self.client.patch(
                    reverse("estudiante-detail", args=[self.est1.id]), {"first_name": "X"}
                ).status_code,
                403,
            )
        self.auth(self.admin)
        self.assertEqual(self.client.post(reverse("grado-list"), payload).status_code, 201)

    def test_no_hay_borrado(self):
        self.auth(self.admin)
        res = self.client.delete(reverse("estudiante-detail", args=[self.est1.id]))
        self.assertEqual(res.status_code, 405)


class AdminCrudTests(AcademicBase):
    def setUp(self):
        super().setUp()
        self.auth(self.admin)

    def test_crear_paralelo_normaliza_el_nombre(self):
        res = self.client.post(reverse("paralelo-list"), {"grado": self.grado7.id, "nombre": " c "})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["nombre"], "C")
        self.assertEqual(res.data["nombre_completo"], "Séptimo EGB C")

    def test_paralelo_duplicado(self):
        res = self.client.post(reverse("paralelo-list"), {"grado": self.grado7.id, "nombre": "a"})
        self.assertEqual(res.status_code, 400)

    def test_asignatura_duplicada_sin_importar_mayusculas(self):
        res = self.client.post(reverse("asignatura-list"), {"nombre": "matemática"})
        self.assertEqual(res.status_code, 400)

    def test_crear_estudiante(self):
        res = self.client.post(
            reverse("estudiante-list"),
            {
                "first_name": "Mia",
                "last_name": "Vera",
                "paralelo": self.par_a.id,
                "representante": self.rep1.id,
            },
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["paralelo_nombre"], "Séptimo EGB A")

    def test_estudiante_con_representante_de_otro_rol(self):
        res = self.client.post(
            reverse("estudiante-list"),
            {
                "first_name": "Mia",
                "last_name": "Vera",
                "paralelo": self.par_a.id,
                "representante": self.doc1.id,
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("representante", res.data)

    def test_estudiante_en_paralelo_inactivo(self):
        self.par_b.is_active = False
        self.par_b.save()
        res = self.client.post(
            reverse("estudiante-list"),
            {
                "first_name": "Mia",
                "last_name": "Vera",
                "paralelo": self.par_b.id,
                "representante": self.rep1.id,
            },
        )
        self.assertEqual(res.status_code, 400)

    def test_mover_estudiante_de_paralelo(self):
        res = self.client.patch(
            reverse("estudiante-detail", args=[self.est1.id]), {"paralelo": self.par_b.id}
        )
        self.assertEqual(res.status_code, 200)
        self.est1.refresh_from_db()
        self.assertEqual(self.est1.paralelo, self.par_b)

    def test_asignacion_con_usuario_que_no_es_docente(self):
        res = self.client.post(
            reverse("asignacion-list"),
            {"docente": self.rep1.id, "paralelo": self.par_a.id, "asignatura": self.lengua.id},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("docente", res.data)

    def test_asignacion_duplicada_por_paralelo_y_asignatura(self):
        res = self.client.post(
            reverse("asignacion-list"),
            {"docente": self.doc2.id, "paralelo": self.par_a.id, "asignatura": self.mate.id},
        )
        self.assertEqual(res.status_code, 400)

    def test_cambiar_el_docente_de_una_asignacion(self):
        res = self.client.patch(
            reverse("asignacion-detail", args=[self.asig1.id]), {"docente": self.doc2.id}
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["docente"], self.doc2.id)
        # doc1 deja de ver el paralelo A.
        self.auth(self.doc1)
        self.assertEqual(self.client.get(reverse("paralelo-list")).data["count"], 0)

    def test_no_desactivar_paralelo_con_estudiantes_activos(self):
        res = self.client.patch(reverse("paralelo-detail", args=[self.par_a.id]), {"is_active": False})
        self.assertEqual(res.status_code, 400)

    def test_no_desactivar_asignatura_con_asignaciones_activas(self):
        res = self.client.patch(reverse("asignatura-detail", args=[self.mate.id]), {"is_active": False})
        self.assertEqual(res.status_code, 400)

    def test_desactivar_asignacion_y_luego_asignatura(self):
        self.client.patch(reverse("asignacion-detail", args=[self.asig1.id]), {"is_active": False})
        res = self.client.patch(reverse("asignatura-detail", args=[self.mate.id]), {"is_active": False})
        self.assertEqual(res.status_code, 200)

    def test_filtros(self):
        res = self.client.get(reverse("estudiante-list"), {"paralelo": self.par_b.id})
        self.assertEqual(self.ids(res), [self.est2.id])
        res = self.client.get(reverse("estudiante-list"), {"search": "pér"})
        self.assertEqual(self.ids(res), [self.est1.id])
        res = self.client.get(reverse("asignacion-list"), {"docente": self.doc2.id})
        self.assertEqual(self.ids(res), [self.asig2.id])

    def test_filtro_con_id_no_numerico(self):
        res = self.client.get(reverse("estudiante-list"), {"paralelo": "abc"})
        self.assertEqual(res.status_code, 400)


class SeedCommandTests(AcademicBase):
    def test_seed_es_idempotente(self):
        call_command("seed_academico", verbosity=0)
        call_command("seed_academico", verbosity=0)
        self.assertEqual(Grado.objects.count(), 10)
        self.assertTrue(Asignatura.objects.filter(nombre="Matemática").exists())
        self.assertEqual(Asignatura.objects.filter(nombre="Matemática").count(), 1)
        # El grado 7 ya existía con otro nombre y se respeta.
        self.assertEqual(Grado.objects.get(orden=7).nombre, "Séptimo EGB")
        