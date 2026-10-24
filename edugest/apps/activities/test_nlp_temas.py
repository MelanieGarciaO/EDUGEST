"""Reconocimiento del tema con el catálogo de temas del grado (con spaCy y con reglas)."""

from . import nlp
from .test_nlp import HOY, LENGUA, MATE, NATURALES, TODAS, MotorBase

TEMAS = [
    (10, "Fracciones", MATE[0]),
    (11, "Fracciones equivalentes", MATE[0]),
    (12, "Operaciones con fracciones", MATE[0]),
    (13, "Fracciones Mixtas", MATE[0]),
    (14, "Números decimales", MATE[0]),
    (15, "Proporcionalidad", MATE[0]),
    (20, "Comprensión lectora", LENGUA[0]),
    (21, "Idea principal", LENGUA[0]),
    (22, "Ortografía", LENGUA[0]),
    (23, "Tipos de texto", LENGUA[0]),
    (30, "Ecosistemas", NATURALES[0]),
    (31, "El cuerpo humano", NATURALES[0]),
]


class TemaCatalogoTests(MotorBase):
    def extraer_t(self, texto, asignaturas=None, temas=TEMAS):
        resultados = [
            nlp.extraer(texto, asignaturas or TODAS, HOY, nlp=m, temas=temas) for m in self.motores()
        ]
        for r in resultados[1:]:
            self.assertEqual(
                (r["tema"], r["asignatura"]), (resultados[0]["tema"], resultados[0]["asignatura"])
            )
        return resultados[0]

    def test_plural_y_singular_coinciden(self):
        r = self.extraer_t("Para el viernes resolver 10 ejercicios de fracciones en Matemática")
        self.assertEqual((r["tema"], r["confianza"]["tema"]), ("Fracciones", "alta"))

    def test_gana_el_subtema_mas_especifico(self):
        r = self.extraer_t("Resolver ejercicios de fracciones equivalentes en Matemática")
        self.assertEqual(r["tema"], "Fracciones equivalentes")
        r = self.extraer_t("Matemática: operaciones con fracciones para el lunes")
        self.assertEqual(r["tema"], "Operaciones con fracciones")

    def test_sin_tildes_ni_mayusculas(self):
        r = self.extraer_t("leer y hacer un resumen de comprension lectora, lengua")
        self.assertEqual(r["tema"], "Comprensión lectora")

    def test_coincidencia_parcial_tiene_confianza_media(self):
        r = self.extraer_t("Ejercicios con decimales en Matemática")
        self.assertEqual((r["tema"], r["confianza"]["tema"]), ("Números decimales", "media"))

    def test_el_tema_indica_la_asignatura_si_no_se_nombra(self):
        r = self.extraer_t("Para mañana dibujar un ecosistema")
        self.assertEqual((r["asignatura"], r["tema"]), (NATURALES[0], "Ecosistemas"))
        self.assertEqual(r["confianza"]["asignatura"], "media")

    def test_solo_temas_de_la_asignatura_reconocida(self):
        # «ortografía» es de Lengua; si la asignatura es Matemática no se mezcla.
        r = self.extraer_t("Matemática: revisar la ortografía de los problemas")
        self.assertEqual(r["tema"], "")

    def test_tema_explicito_usa_el_nombre_oficial(self):
        r = self.extraer_t("Matemática, tema: fracciones mixtas. Resolver la página 30")
        self.assertEqual(r["tema"], "Fracciones Mixtas")

    def test_palabra_generica_sola_no_basta(self):
        r = self.extraer_t("Lengua: escribir un texto corto")
        self.assertEqual(r["tema"], "")

    def test_sin_catalogo_se_comporta_como_antes(self):
        r = self.extraer_t("Resolver ejercicios de fracciones en Matemática", temas=None)
        self.assertEqual(r["tema"], "")
