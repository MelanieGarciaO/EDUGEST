"""
Validación de entradas de texto y protección de los Excel generados.

- Nombres de personas (usuarios y estudiantes): solo letras, 2 o más.
- Paralelo: letras y números. Tema y asignatura: al menos una letra.
- Actividad: descripción mínima y fecha de entrega hasta un año desde hoy.
- Excel: ningún texto que empiece con «=» se guarda como fórmula.
"""

import io
from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from openpyxl import Workbook, load_workbook

from apps.academic.models import Estudiante
from apps.activities.models import Actividad
from apps.grades import excel as grades_excel
from apps.reinforcement.tests import HOY, RefuerzoBase
from apps.security.validadores import nombre_persona

from . import exportar
from .datos import Reporte, Seccion
from .excel_seguro import proteger_formulas

FORMULA = '=HYPERLINK("https://ejemplo.com","clic")'


class NombrePersonaTests(RefuerzoBase):
    def crear_usuario(self, **cambios):
        self.auth(self.admin)
        datos = {"email": "nuevo@edugest.test", "first_name": "Ana", "last_name": "Ruiz", "role": "DOCENTE", **cambios}
        return self.client.post(reverse("user-list"), datos, format="json")

    def test_validador(self):
        for valido, esperado in (
            ("  María   José ", "María José"), ("O'Neil", "O'Neil"), ("Pérez-Gil", "Pérez-Gil"),
            ("Ñúñez Güiza", "Ñúñez Güiza"), ("Lu", "Lu"),
        ):
            self.assertEqual(nombre_persona(valido), esperado)
        for invalido in ("A", "12345", "Ana2", "L@#$%", "<script>", "Ana_María", "-Ana", "Ana--Gil", "   "):
            with self.assertRaises(Exception, msg=invalido):
                nombre_persona(invalido)

    def test_usuario(self):
        for nombre in ("12345", "<script>alert(1)</script>", "A"):
            res = self.crear_usuario(first_name=nombre)
            self.assertEqual(res.status_code, 400, nombre)
            self.assertIn("first_name", res.data)
        res = self.crear_usuario(last_name="Ruiz 2")
        self.assertIn("sin números ni símbolos", str(res.data["last_name"]))
        res = self.crear_usuario(first_name="  Ana   María ")
        self.assertEqual((res.status_code, res.data["first_name"]), (201, "Ana María"))
        # Edición: la misma regla.
        url = reverse("user-detail", args=[self.doc1.id])
        self.assertEqual(self.client.patch(url, {"first_name": "Doc1"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"first_name": "Doña Inés"}, format="json").status_code, 200)

    def test_estudiante(self):
        self.auth(self.admin)
        url = reverse("estudiante-list")
        base = {"first_name": "Leo", "last_name": "Paz", "paralelo": self.par_a.id, "representante": self.rep1.id}
        for campo, valor in (("first_name", "999"), ("first_name", "L@#$%"), ("last_name", "P")):
            res = self.client.post(url, {**base, campo: valor}, format="json")
            self.assertEqual(res.status_code, 400, valor)
            self.assertIn(campo, res.data)
        res = self.client.post(url, {**base, "first_name": "José Ñúñez"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)


class EstructuraTests(RefuerzoBase):
    def test_paralelo(self):
        self.auth(self.admin)
        url = reverse("paralelo-list")
        for nombre in ("#$", "A-1", "B!"):
            self.assertEqual(self.client.post(url, {"grado": self.grado7.id, "nombre": nombre}, format="json").status_code, 400, nombre)
        res = self.client.post(url, {"grado": self.grado7.id, "nombre": " c "}, format="json")
        self.assertEqual((res.status_code, res.data["nombre"]), (201, "C"))

    def test_tema_y_asignatura_con_letras(self):
        self.auth(self.admin)
        res = self.client.post(reverse("tema-list"), {"grado": self.grado7.id, "asignatura": self.mate.id, "nombre": "123"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("nombre", res.data)
        res = self.client.post(reverse("tema-list"), {"grado": self.grado7.id, "asignatura": self.mate.id, "nombre": "Potencias  de 10"}, format="json")
        self.assertEqual((res.status_code, res.data["nombre"]), (201, "Potencias de 10"))
        self.assertEqual(self.client.post(reverse("asignatura-list"), {"nombre": "#123"}, format="json").status_code, 400)


@patch("django.utils.timezone.localdate", return_value=HOY)
class ActividadEntradasTests(RefuerzoBase):
    def publicar(self, **cambios):
        self.auth(self.doc1)
        datos = {"paralelo": self.par_a.id, "asignatura": self.mate.id, "descripcion": "Páginas 20 y 21",
                 "fecha_entrega": str(HOY + timedelta(days=3)), **cambios}
        return self.post(reverse("actividad-list"), datos)

    def test_descripcion_minima(self, _hoy):
        res = self.publicar(descripcion="abc")
        self.assertEqual(res.status_code, 400)
        self.assertIn("al menos 5 caracteres", str(res.data["descripcion"]))
        self.assertEqual(self.publicar(descripcion="Leer").status_code, 400)
        self.assertEqual(self.publicar(descripcion="Leer p. 4").status_code, 201)

    def test_fecha_hasta_un_anio(self, _hoy):
        res = self.publicar(fecha_entrega=str(HOY + timedelta(days=366)))
        self.assertEqual(res.status_code, 400)
        self.assertIn("un año desde hoy", str(res.data["fecha_entrega"]))
        self.assertEqual(self.publicar(fecha_entrega=str(HOY + timedelta(days=365))).status_code, 201)
        # También al editar.
        act = Actividad.objects.create(asignacion=self.asig1, creada_por=self.doc1, descripcion="Tarea uno", fecha_entrega=HOY)
        res = self.client.patch(reverse("actividad-detail", args=[act.id]), {"fecha_entrega": "2062-10-01"}, format="json")
        self.assertEqual(res.status_code, 400)


class ExcelSinFormulasTests(RefuerzoBase):
    def test_proteger_formulas(self):
        wb = Workbook()
        ws = wb.active
        ws["A1"] = FORMULA
        ws["A2"] = "+1-2"
        self.assertEqual(ws["A1"].data_type, "f")  # así lo marca openpyxl por defecto
        proteger_formulas(wb)
        salida = io.BytesIO()
        wb.save(salida)
        leido = load_workbook(io.BytesIO(salida.getvalue())).active
        self.assertEqual((leido["A1"].data_type, leido["A1"].value), ("s", FORMULA))

    def test_reporte_excel(self):
        reporte = Reporte(
            clave="prueba", titulo="Prueba", descripcion="", filtros=[("Estudiante", FORMULA)],
            secciones=[Seccion(titulo="Datos", columnas=[("Nombre", 1), ("Nota", 1)], filas=[[FORMULA, 8]], nota=FORMULA)],
            generado_por=FORMULA,
        )
        ws = load_workbook(io.BytesIO(exportar.a_xlsx(reporte))).worksheets[0]
        formulas = [c.coordinate for fila in ws.iter_rows() for c in fila if c.data_type == "f"]
        self.assertEqual(formulas, [])
        self.assertIn(FORMULA, [c.value for fila in ws.iter_rows() for c in fila])

    def test_plantilla_de_notas(self):
        # Un nombre guardado antes de la validación (o por otra vía) no se ejecuta en Excel.
        Estudiante.objects.filter(pk=self.est1.pk).update(first_name=FORMULA)
        act = Actividad.objects.create(asignacion=self.asig1, creada_por=self.doc1, descripcion=FORMULA, fecha_entrega=HOY)
        contenido = grades_excel.generar_plantilla(act, Estudiante.objects.filter(paralelo=self.par_a).order_by("id"), {})
        ws = load_workbook(io.BytesIO(contenido)).active
        self.assertEqual([c.coordinate for fila in ws.iter_rows() for c in fila if c.data_type == "f"], [])


class AdminDjangoNombresTests(RefuerzoBase):
    def test_formularios_del_admin(self):
        from apps.academic.admin import EstudianteAdminForm
        from apps.security.admin import CustomUserChangeForm

        datos = {"first_name": "Leo2", "last_name": "Paz", "paralelo": self.par_a.id, "representante": self.rep1.id, "is_active": True}
        form = EstudianteAdminForm(data=datos)
        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
        form = EstudianteAdminForm(data={**datos, "first_name": "  Leo   Ángel "})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["first_name"], "Leo Ángel")

        form = CustomUserChangeForm(instance=self.doc1, data={
            "email": self.doc1.email, "first_name": "<b>", "last_name": "Ruiz", "role": self.doc1.role,
            "date_joined": "2026-01-01 00:00:00", "terminos_version": "", "is_active": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("first_name", form.errors)
