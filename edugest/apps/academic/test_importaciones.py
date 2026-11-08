"""Importación masiva de estudiantes y asignaciones desde Excel/CSV (solo administrador)."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook, load_workbook

from apps.security.models import Role, User

from .models import AsignacionDocente, Asignatura, Estudiante
from .tests import AcademicBase, make_user


def xlsx(filas):
    wb = Workbook()
    for f in filas:
        wb.active.append(f)
    salida = BytesIO()
    wb.save(salida)
    return SimpleUploadedFile("datos.xlsx", salida.getvalue())


def csv(texto, nombre="datos.csv", codificacion="utf-8-sig"):
    return SimpleUploadedFile(nombre, texto.encode(codificacion))


class ImportacionBase(AcademicBase):
    def subir(self, recurso, archivo, confirmar=False, user=None):
        self.auth(user or self.admin)
        datos = {"archivo": archivo, "confirmar": "true" if confirmar else "false"}
        return self.client.post(reverse(f"{recurso}-importar"), datos, format="multipart")

    @staticmethod
    def estados(res):
        return [(f["fila"], f["estado"]) for f in res.data["filas"]]


class EstudiantesTests(ImportacionBase):
    CAB = ["Nombres", "Apellidos", "Paralelo", "Correo del representante"]

    def test_vista_previa_no_guarda(self):
        res = self.subir("estudiante", xlsx([self.CAB, ["Ana", "Ruiz", "Séptimo EGB A", "rep1@edugest.test"]]))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["total"], res.data["validas"], res.data["errores"]), (1, 1, 0))
        self.assertEqual(res.data["filas"][0]["datos"]["paralelo"], "Séptimo EGB A")
        self.assertEqual(res.data["filas"][0]["datos"]["representante"], "Nombre rep1")
        self.assertEqual(Estudiante.objects.count(), 2)

    def test_confirmar_registra(self):
        archivo = [self.CAB, ["Ana", "Ruiz", "septimo egb a", "REP1@edugest.test"],
                   ["Juan", "Vera", "Séptimo EGB B", "Nombre rep2"], [None, None, None, None]]
        res = self.subir("estudiante", xlsx(archivo), confirmar=True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["creados"], 2)
        ana = Estudiante.objects.get(first_name="Ana")
        self.assertEqual((ana.paralelo, ana.representante), (self.par_a, self.rep1))
        self.assertEqual(Estudiante.objects.get(first_name="Juan").representante, self.rep2)

    def test_omite_los_ya_registrados(self):
        res = self.subir("estudiante", xlsx([self.CAB, ["luis", "PÉREZ", "Séptimo EGB A", "rep1@edugest.test"]]), True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["omitidas"], res.data["creados"]), (1, 0))
        self.assertEqual(Estudiante.objects.count(), 2)

    def test_errores_por_fila_y_todo_o_nada(self):
        make_user("doc9@edugest.test", Role.DOCENTE)
        archivo = [
            self.CAB,
            ["Ana", "Ruiz", "Séptimo EGB A", "rep1@edugest.test"],   # 2 ok
            ["Ana", "Ruiz", "Séptimo EGB A", "rep1@edugest.test"],   # 3 repetida
            ["Leo", "Paz", "Octavo EGB A", "rep1@edugest.test"],     # 4 paralelo inexistente
            ["Eva", "Sol", "Séptimo EGB A", "doc9@edugest.test"],    # 5 no es representante
            ["", "Gil", "Séptimo EGB A", "rep1@edugest.test"],       # 6 sin nombres
        ]
        res = self.subir("estudiante", xlsx(archivo))
        self.assertEqual(self.estados(res), [(2, "ok"), (3, "error"), (4, "error"), (5, "error"), (6, "error")])
        self.assertIn("Repetido en el archivo (fila 2)", res.data["filas"][1]["mensajes"][0])
        self.assertIn("Octavo EGB A", res.data["filas"][2]["mensajes"][0])

        res = self.subir("estudiante", xlsx(archivo), confirmar=True)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["vista_previa"]["errores"], 4)
        self.assertEqual(Estudiante.objects.count(), 2)

    def test_csv_con_punto_y_coma_y_grado_separado(self):
        texto = "Nombres;Apellidos;Grado;Paralelo;Representante\nMía;Luna;Séptimo EGB;B;rep2@edugest.test\n"
        res = self.subir("estudiante", csv(texto), confirmar=True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Estudiante.objects.get(first_name="Mía").paralelo, self.par_b)

    def test_csv_latin1(self):
        texto = "Nombres,Apellidos,Paralelo,Correo del representante\nMaría,Peña,Séptimo EGB A,rep1@edugest.test\n"
        res = self.subir("estudiante", csv(texto, codificacion="latin-1"))
        self.assertEqual(res.data["validas"], 1)

    def test_requiere_representante_activo(self):
        User.objects.filter(role=Role.REPRESENTANTE).update(is_active=False)
        res = self.subir("estudiante", xlsx([self.CAB, ["Ana", "Ruiz", "Séptimo EGB A", "rep1@edugest.test"]]))
        self.assertEqual(res.status_code, 400)
        self.assertIn("representante", str(res.data["archivo"]))
        self.auth(self.admin)
        self.assertEqual(self.client.get(reverse("estudiante-plantilla")).status_code, 400)

    def test_archivos_invalidos(self):
        self.assertEqual(self.subir("estudiante", SimpleUploadedFile("a.txt", b"x")).status_code, 400)
        self.assertEqual(self.subir("estudiante", SimpleUploadedFile("a.xlsx", b"no excel")).status_code, 400)
        res = self.subir("estudiante", xlsx([["Columna", "Otra"], ["a", "b"]]))
        self.assertIn("columnas obligatorias", str(res.data["archivo"]))
        self.assertEqual(self.subir("estudiante", xlsx([self.CAB])).status_code, 400)  # sin filas

    def test_solo_administrador(self):
        archivo = xlsx([self.CAB, ["Ana", "Ruiz", "Séptimo EGB A", "rep1@edugest.test"]])
        self.assertEqual(self.subir("estudiante", archivo, user=self.doc1).status_code, 403)
        self.auth(self.rep1)
        self.assertEqual(self.client.get(reverse("estudiante-plantilla")).status_code, 403)

    def test_plantilla_sirve_para_importar(self):
        self.auth(self.admin)
        res = self.client.get(reverse("estudiante-plantilla"))
        self.assertEqual(res.status_code, 200)
        wb = load_workbook(BytesIO(res.content))
        self.assertEqual(wb.sheetnames, ["Estudiantes", "Opciones", "Instrucciones"])
        self.assertIn("Séptimo EGB A", [c.value for c in wb["Opciones"]["A"]])
        self.assertTrue(wb["Estudiantes"].data_validations.dataValidation)
        ws = wb["Estudiantes"]
        ws.append(["Ana", "Ruiz", None, "Séptimo EGB A", "rep1@edugest.test"])
        salida = BytesIO()
        wb.save(salida)
        res = self.subir("estudiante", SimpleUploadedFile("plantilla.xlsx", salida.getvalue()), confirmar=True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["creados"], 1)


class AsignacionesTests(ImportacionBase):
    CAB = ["Correo del docente", "Paralelo", "Asignatura"]

    def test_confirmar_registra(self):
        res = self.subir("asignacion", xlsx([self.CAB, ["doc1@edugest.test", "Séptimo EGB B", "matematica"]]), True)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertTrue(AsignacionDocente.objects.filter(docente=self.doc1, paralelo=self.par_b, asignatura=self.mate).exists())

    def test_reglas_de_unicidad(self):
        AsignacionDocente.objects.create(docente=self.doc2, paralelo=self.par_a, asignatura=self.lengua, is_active=False)
        archivo = [
            self.CAB,
            ["doc1@edugest.test", "Séptimo EGB A", "Matemática"],             # 2 ya existe -> omitida
            ["doc2@edugest.test", "Séptimo EGB A", "Matemática"],             # 3 la dicta doc1 -> error
            ["doc2@edugest.test", "Séptimo EGB A", "Lengua y Literatura"],    # 4 existe inactiva -> error
            ["doc1@edugest.test", "Séptimo EGB B", "Matemática"],             # 5 ok
            ["doc2@edugest.test", "Séptimo EGB B", "Matemática"],             # 6 repetida en archivo
            ["rep1@edugest.test", "Séptimo EGB B", "Ciencias"],               # 7 no docente + asignatura
        ]
        res = self.subir("asignacion", xlsx(archivo))
        self.assertEqual(self.estados(res), [(2, "omitida"), (3, "error"), (4, "error"), (5, "ok"), (6, "error"), (7, "error")])
        self.assertIn("ya la dicta Nombre doc1", res.data["filas"][1]["mensajes"][0])
        self.assertEqual(len(res.data["filas"][5]["mensajes"]), 2)

    def test_asignatura_inactiva(self):
        Asignatura.objects.create(nombre="Inglés", is_active=False)
        res = self.subir("asignacion", xlsx([self.CAB, ["doc1@edugest.test", "Séptimo EGB B", "Inglés"]]))
        self.assertEqual(res.data["errores"], 1)

    def test_requiere_docente_activo(self):
        User.objects.filter(role=Role.DOCENTE).update(is_active=False)
        res = self.subir("asignacion", xlsx([self.CAB, ["doc1@edugest.test", "Séptimo EGB B", "Matemática"]]))
        self.assertEqual(res.status_code, 400)
        self.assertIn("docente", str(res.data["archivo"]))

    def test_plantilla(self):
        self.auth(self.admin)
        wb = load_workbook(BytesIO(self.client.get(reverse("asignacion-plantilla")).content))
        opciones = [c.value for fila in wb["Opciones"].iter_rows() for c in fila]
        self.assertIn("doc1@edugest.test", opciones)
        self.assertIn("Matemática", opciones)
