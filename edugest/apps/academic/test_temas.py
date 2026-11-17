from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from .models import Grado, Tema
from .tests import AcademicBase


class TemaTests(AcademicBase):
    def setUp(self):
        super().setUp()
        self.fracciones = Tema.objects.create(
            grado=self.grado7, asignatura=self.mate, nombre="Fracciones"
        )
        self.equivalentes = Tema.objects.create(
            grado=self.grado7, asignatura=self.mate, padre=self.fracciones,
            nombre="Fracciones equivalentes",
        )

    def datos(self, **cambios):
        datos = {"grado": self.grado7.id, "asignatura": self.mate.id, "nombre": "Decimales"}
        datos.update(cambios)
        return datos

    def test_admin_crea_tema_y_subtema(self):
        self.auth(self.admin)
        res = self.client.post(reverse("tema-list"), self.datos())
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["es_subtema"])
        self.assertIsNone(res.data["padre_nombre"])

        res = self.client.post(
            reverse("tema-list"),
            self.datos(nombre="Operaciones", padre=self.fracciones.id),
        )
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["es_subtema"])
        self.assertEqual(res.data["padre_nombre"], "Fracciones")

    def test_lectura_para_todos_y_escritura_solo_admin(self):
        for user in (self.doc1, self.rep1):
            self.auth(user)
            self.assertEqual(self.client.get(reverse("tema-list")).status_code, 200)
            self.assertEqual(self.client.post(reverse("tema-list"), self.datos()).status_code, 403)

    def test_nombre_duplicado_sin_importar_mayusculas(self):
        self.auth(self.admin)
        res = self.client.post(reverse("tema-list"), self.datos(nombre="fracciones"))
        self.assertEqual(res.status_code, 400)
        res = self.client.post(
            reverse("tema-list"),
            self.datos(nombre="FRACCIONES EQUIVALENTES", padre=self.fracciones.id),
        )
        self.assertEqual(res.status_code, 400)

    def test_mismo_nombre_en_otra_asignatura_es_valido(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("tema-list"), self.datos(asignatura=self.lengua.id, nombre="Fracciones")
        )
        self.assertEqual(res.status_code, 201)

    def test_un_subtema_no_puede_tener_subtemas(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("tema-list"), self.datos(nombre="Otro", padre=self.equivalentes.id)
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("padre", res.data)

    def test_el_padre_debe_ser_del_mismo_grado_y_asignatura(self):
        self.auth(self.admin)
        res = self.client.post(
            reverse("tema-list"),
            self.datos(asignatura=self.lengua.id, nombre="Otro", padre=self.fracciones.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("padre", res.data)

    def test_no_se_puede_mover_un_tema(self):
        self.auth(self.admin)
        res = self.client.patch(
            reverse("tema-detail", args=[self.fracciones.id]), {"asignatura": self.lengua.id}
        )
        self.assertEqual(res.status_code, 400)
        res = self.client.patch(
            reverse("tema-detail", args=[self.equivalentes.id]), {"padre": None}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    def test_renombrar_y_desactivar(self):
        self.auth(self.admin)
        res = self.client.patch(reverse("tema-detail", args=[self.equivalentes.id]), {"nombre": "Equivalencia"})
        self.assertEqual(res.status_code, 200)
        # No se desactiva un tema con subtemas activos; primero el subtema.
        res = self.client.patch(reverse("tema-detail", args=[self.fracciones.id]), {"is_active": False})
        self.assertEqual(res.status_code, 400)
        self.client.patch(reverse("tema-detail", args=[self.equivalentes.id]), {"is_active": False})
        res = self.client.patch(reverse("tema-detail", args=[self.fracciones.id]), {"is_active": False})
        self.assertEqual(res.status_code, 200)

    def test_no_hay_borrado(self):
        self.auth(self.admin)
        self.assertEqual(self.client.delete(reverse("tema-detail", args=[self.fracciones.id])).status_code, 405)

    def test_filtros(self):
        self.auth(self.admin)
        raiz = self.client.get(reverse("tema-list"), {"padre": "null"})
        self.assertEqual(self.ids(raiz), [self.fracciones.id])
        hijos = self.client.get(reverse("tema-list"), {"padre": self.fracciones.id})
        self.assertEqual(self.ids(hijos), [self.equivalentes.id])
        por_asig = self.client.get(reverse("tema-list"), {"asignatura": self.lengua.id})
        self.assertEqual(por_asig.data["count"], 0)
        self.assertEqual(self.client.get(reverse("tema-list"), {"grado": "x"}).status_code, 400)


class SeedTemasTests(AcademicBase):
    def test_falla_con_mensaje_claro_si_faltan_asignaturas_base(self):
        # En este setUp existe el grado 7 pero no "Ciencias Naturales".
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_temas_ejemplo", verbosity=0)
        self.assertIn("seed_academico", str(ctx.exception))
        self.assertEqual(Tema.objects.count(), 0)  # la carga es atómica


    def test_es_idempotente(self):
        call_command("seed_academico", verbosity=0)
        call_command("seed_temas_ejemplo", verbosity=0)
        total = Tema.objects.count()
        call_command("seed_temas_ejemplo", verbosity=0)
        self.assertEqual(Tema.objects.count(), total)
        self.assertTrue(
            Tema.objects.filter(nombre="Fracciones equivalentes", padre__nombre="Fracciones").exists()
        )


class TemasPropiosDocenteTests(AcademicBase):
    """?propios=true: el docente solo ve los temas de sus asignaturas en el grado de sus paralelos."""

    def setUp(self):
        super().setUp()
        self.grado5 = Grado.objects.create(nombre="Quinto EGB", orden=5)
        self.mate7 = Tema.objects.create(grado=self.grado7, asignatura=self.mate, nombre="Fracciones")
        self.sub_mate7 = Tema.objects.create(
            grado=self.grado7, asignatura=self.mate, padre=self.mate7, nombre="Fracciones mixtas"
        )
        self.lengua7 = Tema.objects.create(grado=self.grado7, asignatura=self.lengua, nombre="Ortografía")
        self.mate5 = Tema.objects.create(grado=self.grado5, asignatura=self.mate, nombre="Operaciones combinadas")
        self.url = reverse("tema-list")

    def ids_propios(self, user, **extra):
        self.auth(user)
        return self.ids(self.client.get(self.url, {"propios": "true", **extra}))

    def test_docente_solo_ve_su_asignatura_y_grado(self):
        # doc1: Matemática en 7.º A -> ni Lengua de 7.º ni Matemática de 5.º
        self.assertEqual(self.ids_propios(self.doc1), sorted([self.mate7.id, self.sub_mate7.id]))
        self.assertEqual(self.ids_propios(self.doc2), [self.lengua7.id])

    def test_asignacion_inactiva_no_cuenta(self):
        self.asig1.is_active = False
        self.asig1.save()
        self.assertEqual(self.ids_propios(self.doc1), [])

    def test_admin_ve_todos_aunque_pida_propios(self):
        self.assertEqual(
            self.ids_propios(self.admin),
            sorted([self.mate7.id, self.sub_mate7.id, self.lengua7.id, self.mate5.id]),
        )

    def test_sin_el_parametro_no_cambia_el_catalogo(self):
        self.auth(self.doc1)
        self.assertEqual(len(self.ids(self.client.get(self.url))), 4)
