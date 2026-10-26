"""Mejora 11: EntityRuler (MATERIAL y alias de ASIGNATURA). Se prueba con spaCy y sin él."""

from . import ner
from .test_nlp import ARTISTICA, FISICA, LENGUA, MATE, NATURALES, MotorBase


class EntityRulerTests(MotorBase):
    def entidades(self, texto):
        resultados = [[(e.etiqueta, e.clave, e.texto) for e in ner.buscar(texto, m)] for m in self.motores()]
        for r in resultados[1:]:
            self.assertEqual(r, resultados[0])  # spaCy y respaldo reconocen lo mismo
        return resultados[0]

    def test_pipeline_incluye_el_entity_ruler(self):
        from . import nlp

        pipeline = nlp.obtener_nlp()
        if pipeline is None:
            self.skipTest("spaCy no está instalado")
        self.assertIn(ner.NOMBRE_COMPONENTE, pipeline.pipe_names)

    def test_materiales_en_plural_sin_tildes_y_compuestos(self):
        ents = self.entidades("Traer tijeras, lapices de colores, goma en barra y compases")
        self.assertEqual(
            [e[2] for e in ents if e[0] == "MATERIAL"],
            ["tijeras", "lapices de colores", "goma en barra", "compases"],
        )

    def test_alias_de_asignatura(self):
        self.assertIn(("ASIGNATURA", "lengua", "lenguaje"), self.entidades("Tarea de lenguaje"))
        self.assertIn(("ASIGNATURA", "fisica", "gimnasia"), self.entidades("Clase de gimnasia"))


class MaterialesNerTests(MotorBase):
    def test_recorta_el_texto_que_no_es_material(self):
        r = self.extraer("Para el lunes traer tijera y goma para la actividad de recorte en Ciencias Naturales")
        self.assertEqual(r["materiales"], ["tijera", "goma"])
        self.assertEqual(r["asignatura"], NATURALES[0])  # ya no queda escondida en la lista
        self.assertEqual(r["descripcion"], "Para la actividad de recorte")

    def test_verbo_de_uso_solo_toma_materiales_reconocidos(self):
        r = self.extraer("Usar regla y compás para medir ángulos en Matemática")
        self.assertEqual(r["materiales"], ["regla", "compás"])
        self.assertEqual(r["confianza"]["materiales"], "media")
        self.assertEqual(r["descripcion"], "Usar regla y compás para medir ángulos")

    def test_verbo_de_uso_sin_materiales_no_inventa(self):
        r = self.extraer("Usar la creatividad para escribir un cuento en Lengua")
        self.assertEqual(r["materiales"], [])

    def test_material_desconocido_tras_traer_se_conserva(self):
        r = self.extraer("Traer semillas de fréjol y algodón")
        self.assertEqual(r["materiales"], ["semillas de fréjol", "algodón"])


class AliasAsignaturaTests(MotorBase):
    def test_lenguaje_es_lengua_y_literatura(self):
        r = self.extraer("En lenguaje leer el cuento de la página 20")
        self.assertEqual((r["asignatura"], r["confianza"]["asignatura"]), (LENGUA[0], "media"))
        self.assertEqual(r["descripcion"], "Leer el cuento de la página 20")

    def test_gimnasia_y_arte(self):
        self.assertEqual(self.extraer("Para gimnasia traer ropa deportiva")["asignatura"], FISICA[0])
        self.assertEqual(self.extraer("Pintar un paisaje en arte")["asignatura"], ARTISTICA[0])

    def test_nombre_oficial_tiene_prioridad_sobre_alias(self):
        r = self.extraer("Matemática: resolver con arte los problemas")
        self.assertEqual(r["asignatura"], MATE[0])

    def test_alias_de_asignatura_no_disponible_no_se_asigna(self):
        r = self.extraer("Tarea de lenguaje", asignaturas=[MATE, NATURALES])
        self.assertIsNone(r["asignatura"])
