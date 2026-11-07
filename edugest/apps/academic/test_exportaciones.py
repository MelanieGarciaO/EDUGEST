"""Exportación a Excel de estudiantes y asignaciones (solo administrador)."""

from io import BytesIO

from django.urls import reverse
from openpyxl import load_workbook

from .models import AsignacionDocente, Estudiante
from .tests import AcademicBase


class ExportacionesTests(AcademicBase):
    def bajar(self, nombre, user=None, **params):
        self.auth(user or self.admin)
        return self.client.get(reverse(f"{nombre}-exportar"), params)

    @staticmethod
    def filas(res):
        ws = load_workbook(BytesIO(res.content)).active
        return [list(f) for f in ws.iter_rows(min_row=7, values_only=True)]

    def test_estudiantes(self):
        Estudiante.objects.create(first_name="Ana", last_name="Zambrano", paralelo=self.par_a,
                                  representante=self.rep1, is_active=False)
        res = self.bajar("estudiante")
        self.assertEqual(res.status_code, 200)
        self.assertIn('filename="edugest_estudiantes_', res["Content-Disposition"])
        filas = self.filas(res)
        self.assertEqual([f[1] for f in filas], ["Mora", "Pérez", "Zambrano"])
        self.assertEqual(filas[1][:8], [2, "Pérez", "Luis", "Séptimo EGB", "A", "Nombre rep1",
                                        "rep1@edugest.test", "Activo"])

    def test_estudiantes_respeta_filtros(self):
        Estudiante.objects.create(first_name="Ana", last_name="Zambrano", paralelo=self.par_a,
                                  representante=self.rep1, is_active=False)
        filas = self.filas(self.bajar("estudiante", paralelo=self.par_a.id, is_active="true"))
        self.assertEqual([f[1] for f in filas], ["Pérez"])
        filas = self.filas(self.bajar("estudiante", search="mor"))
        self.assertEqual([f[1] for f in filas], ["Mora"])
        filas = self.filas(self.bajar("estudiante", search="xyz"))
        self.assertEqual(filas[0][0], "No hay estudiantes con los filtros seleccionados.")

    def test_asignaciones(self):
        AsignacionDocente.objects.create(docente=self.doc1, paralelo=self.par_b, asignatura=self.mate,
                                         is_active=False)
        filas = self.filas(self.bajar("asignacion"))
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[0][:8], [1, "Séptimo EGB", "A", "Matemática", "Nombre doc1",
                                        "doc1@edugest.test", 1, "Activa"])
        filas = self.filas(self.bajar("asignacion", docente=self.doc1.id, is_active="true"))
        self.assertEqual(len(filas), 1)

    def test_solo_administrador(self):
        for user in (self.doc1, self.rep1):
            self.assertEqual(self.bajar("estudiante", user).status_code, 403)
            self.assertEqual(self.bajar("asignacion", user).status_code, 403)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("estudiante-exportar")).status_code, 401)

    def test_filtro_invalido(self):
        self.assertEqual(self.bajar("estudiante", paralelo="x").status_code, 400)
