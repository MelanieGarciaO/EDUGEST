"""Mejora 12: importar notas desde cualquier Excel o CSV (mapeo inteligente de columnas)."""

from io import BytesIO

from openpyxl import Workbook

from .models import Calificacion
from .test_excel import ExcelBase


def xlsx(filas):
    wb = Workbook()
    for fila in filas:
        wb.active.append(fila)
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


class MapeoTests(ExcelBase):
    # Paralelo A: Luis Pérez (est1) y Marta Vera (est3).

    def test_planilla_propia_con_titulo_y_columnas_extra(self):
        contenido = xlsx([
            ["Unidad Educativa X — Registro de notas"],
            [],
            ["N°", "Apellidos y nombres", "Fecha", "Nota final"],
            [1, "PÉREZ LUIS", "20/10/2026", 8.5],
            [2, "Vera Marta", "20/10/2026", "6,25"],
        ])
        res = self.subir(contenido)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["modo"], "mapeo")
        self.assertEqual(res.data["mapeo"]["titulos_nombre"], ["Apellidos y nombres"])
        self.assertEqual(
            [(f["estudiante"], f["valor"], f["confianza"]) for f in res.data["filas"]],
            [(self.est1.id, "8.50", "alta"), (self.est3.id, "6.25", "alta")],
        )
        self.assertFalse(Calificacion.objects.exists())

    def test_apellidos_y_nombres_en_columnas_separadas(self):
        contenido = xlsx([["Apellidos", "Nombres", "Calificación"], ["Pérez", "Luis", 9], ["Vera", "Marta", 7]])
        res = self.subir(contenido)
        self.assertEqual(len(res.data["filas"]), 2)

    def test_varias_columnas_de_nota_sugiere_promedio_y_permite_elegir(self):
        contenido = xlsx([["Estudiante", "Nota 1", "Nota 2", "Promedio"], ["Luis Pérez", 6, 8, 7], ["Marta Vera", 9, 10, 9.5]])
        res = self.subir(contenido)
        self.assertEqual(len(res.data["mapeo"]["columnas_nota"]), 3)
        self.assertEqual(res.data["mapeo"]["columna_nota"], 3)
        self.assertEqual(res.data["filas"][0]["valor"], "7.00")
        self.auth(self.doc1)
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse
        res = self.client.post(
            reverse("actividad-calificaciones-importar", args=[self.act1.id]),
            {"archivo": SimpleUploadedFile("n.xlsx", contenido), "columna_nota": "1"},
            format="multipart",
        )
        self.assertEqual(res.data["filas"][0]["valor"], "6.00")

    def test_sin_encabezados_detecta_por_contenido(self):
        res = self.subir(xlsx([["Luis Pérez", 8], ["Marta Vera", 4]]))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data["filas"]), 2)

    def test_csv_con_punto_y_coma(self):
        contenido = "Alumno;Nota\nPerez Luis;9,5\nMarta Vera;7\n".encode("latin-1")
        res = self.subir(contenido, nombre="notas.csv")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([f["valor"] for f in res.data["filas"]], ["9.50", "7.00"])

    def test_errores_de_tipeo_ambiguos_y_desconocidos(self):
        res = self.subir(xlsx([
            ["Estudiante", "Nota"], ["Luiz Peres", 8], ["Pedro Mora", 7], ["Marta Vera", 15],
        ]))
        self.assertEqual([(f["estudiante"], f["confianza"]) for f in res.data["filas"]], [(self.est1.id, "media")])
        mensajes = " | ".join(e["mensaje"] for e in res.data["errores"])
        self.assertIn("no coincide con ningún estudiante", mensajes)
        self.assertIn("entre 0 y 10", mensajes)

    def test_archivo_sin_columnas_reconocibles(self):
        res = self.subir(xlsx([["hola", "mundo"], ["sin", "notas"]]))
        self.assertEqual(res.status_code, 400)
