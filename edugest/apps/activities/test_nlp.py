"""
Pruebas del motor de extracción. Se ejecutan con el pipeline de spaCy (si el modelo está
instalado) y también en modo de respaldo solo con reglas, para comprobar que ambos
caminos dan el mismo resultado.

Fecha de referencia: jueves 1 de octubre de 2026.
"""

from datetime import date

from django.test import SimpleTestCase

from . import nlp

HOY = date(2026, 10, 1)  # jueves
MATE = (1, "Matemática")
LENGUA = (2, "Lengua y Literatura")
NATURALES = (3, "Ciencias Naturales")
SOCIALES = (4, "Estudios Sociales")
FISICA = (5, "Educación Física")
ARTISTICA = (6, "Educación Cultural y Artística")
INGLES = (7, "Inglés")
TODAS = [MATE, LENGUA, NATURALES, SOCIALES, FISICA, ARTISTICA, INGLES]


class MotorBase(SimpleTestCase):
    """Cada prueba se repite con spaCy y con el respaldo de reglas."""

    def motores(self):
        motores = [None]
        pipeline = nlp.obtener_nlp()
        if pipeline is not None:
            motores.append(pipeline)
        return motores

    def extraer(self, texto, asignaturas=None, hoy=HOY):
        resultados = []
        for motor in self.motores():
            resultados.append(nlp.extraer(texto, asignaturas or TODAS, hoy, nlp=motor))
        # Ambos motores deben coincidir en los datos (no en el campo "motor").
        base = {k: v for k, v in resultados[0].items() if k != "motor"}
        for otro in resultados[1:]:
            self.assertEqual(base, {k: v for k, v in otro.items() if k != "motor"})
        return resultados[-1]


class EjemplosDelDocumentoTests(MotorBase):
    def test_ejemplo_de_la_imagen(self):
        r = self.extraer(
            "Para el próximo lunes realizar las páginas 20 y 21 de Matemáticas "
            "y traer regla, compás y cartulina."
        )
        self.assertEqual(r["asignatura"], 1)
        self.assertEqual(r["descripcion"], "Realizar las páginas 20 y 21")
        self.assertEqual(r["fecha_entrega"], "2026-10-05")
        self.assertEqual(r["materiales"], ["regla", "compás", "cartulina"])
        self.assertEqual(r["campos_vacios"], [])

    def test_proyecto_con_fecha_explicita(self):
        r = self.extraer(
            "Proyecto en grupo de Ciencias Naturales para el 20 de octubre, "
            "traer cartulina y marcadores"
        )
        self.assertEqual(r["asignatura_nombre"], "Ciencias Naturales")
        self.assertEqual(r["confianza"]["asignatura"], "alta")
        self.assertEqual(r["descripcion"], "Proyecto en grupo")
        self.assertEqual(r["fecha_entrega"], "2026-10-20")
        self.assertEqual(r["materiales"], ["cartulina", "marcadores"])

    def test_sin_fecha_ni_asignatura_deja_campos_vacios(self):
        r = self.extraer("Leer el capítulo 3 del libro")
        self.assertIsNone(r["asignatura"])
        self.assertIsNone(r["fecha_entrega"])
        self.assertEqual(r["descripcion"], "Leer el capítulo 3 del libro")
        self.assertEqual(r["campos_vacios"], ["asignatura", "fecha_entrega"])

    def test_asignatura_unica_se_infiere_con_confianza_media(self):
        r = self.extraer("Leer el capítulo 3 del libro", asignaturas=[LENGUA])
        self.assertEqual(r["asignatura"], 2)
        self.assertEqual(r["confianza"]["asignatura"], "media")
        self.assertTrue(r["advertencias"])


class FechasTests(MotorBase):
    def fecha(self, texto, hoy=HOY):
        return self.extraer(texto, hoy=hoy)["fecha_entrega"]

    def test_hoy_manana_y_pasado_manana(self):
        self.assertEqual(self.fecha("Estudiar para hoy"), "2026-10-01")
        self.assertEqual(self.fecha("Terminar la lámina para mañana"), "2026-10-02")
        self.assertEqual(self.fecha("Entregar pasado mañana"), "2026-10-03")

    def test_manana_como_parte_del_dia_no_es_fecha(self):
        r = self.extraer("Practicar lectura en la mañana")
        self.assertIsNone(r["fecha_entrega"])

    def test_dia_de_la_semana(self):
        self.assertEqual(self.fecha("Entregar el viernes"), "2026-10-02")
        self.assertEqual(self.fecha("Entregar el lunes"), "2026-10-05")
        # Hoy es jueves: "el jueves" es el de la semana siguiente.
        self.assertEqual(self.fecha("Entregar el jueves"), "2026-10-08")
        self.assertEqual(self.fecha("Entregar el miércoles próximo"), "2026-10-07")

    def test_dia_de_la_proxima_semana(self):
        self.assertEqual(self.fecha("Entregar el viernes de la próxima semana"), "2026-10-09")

    def test_fecha_explicita_con_y_sin_anio(self):
        self.assertEqual(self.fecha("Entregar el 5 de octubre de 2026"), "2026-10-05")
        self.assertEqual(self.fecha("Entregar para el 15 de octubre"), "2026-10-15")
        self.assertEqual(self.fecha("Entregar el lunes 12 de octubre"), "2026-10-12")

    def test_fecha_numerica(self):
        self.assertEqual(self.fecha("Entregar para el 15/10/2026"), "2026-10-15")
        self.assertEqual(self.fecha("Entregar para el 15/10"), "2026-10-15")

    def test_numeros_que_no_son_fechas(self):
        self.assertIsNone(self.fecha("Resolver las fracciones 3/4 y 1/2"))
        self.assertIsNone(self.fecha("Leer las páginas 10-12"))

    def test_solo_el_dia_del_mes(self):
        self.assertEqual(self.fecha("Entregar para el 15."), "2026-10-15")

    def test_en_n_dias(self):
        self.assertEqual(self.fecha("Entregar en 3 días"), "2026-10-04")
        self.assertEqual(self.fecha("Entregar en dos semanas"), "2026-10-15")

    def test_cambio_de_anio_cercano(self):
        r = self.extraer("Entregar para el 10 de enero", hoy=date(2026, 12, 20))
        self.assertEqual(r["fecha_entrega"], "2027-01-10")

    def test_fecha_pasada_se_advierte(self):
        r = self.extraer("Entregar para el 30 de septiembre")
        self.assertEqual(r["fecha_entrega"], "2026-09-30")
        self.assertTrue(any("ya pasó" in a for a in r["advertencias"]))

    def test_varias_fechas_toma_la_primera_y_advierte(self):
        r = self.extraer("Tarea para el lunes y evaluación el 20 de octubre")
        self.assertEqual(r["fecha_entrega"], "2026-10-05")
        self.assertTrue(any("varias fechas" in a for a in r["advertencias"]))

    def test_fecha_inexistente_se_ignora(self):
        r = self.extraer("Entregar para el 31 de noviembre")
        self.assertIsNone(r["fecha_entrega"])


class AsignaturaTests(MotorBase):
    def asignatura(self, texto, asignaturas=None):
        return self.extraer(texto, asignaturas)["asignatura_nombre"]

    def test_plural_mayusculas_y_tildes(self):
        self.assertEqual(self.asignatura("Ejercicios de MATEMATICAS"), "Matemática")
        self.assertEqual(self.asignatura("Tarea de matemática"), "Matemática")

    def test_abreviatura(self):
        self.assertEqual(self.asignatura("Tarea de mate para el lunes"), "Matemática")

    def test_palabra_distintiva(self):
        self.assertEqual(self.asignatura("Lectura de lengua"), "Lengua y Literatura")
        self.assertEqual(self.asignatura("Trabajo de naturales"), "Ciencias Naturales")
        self.assertEqual(self.asignatura("Educación física: traer ropa deportiva"), "Educación Física")

    def test_palabra_generica_sola_no_identifica(self):
        self.assertIsNone(self.asignatura("Hacer un estudio del tema"))

    def test_dos_asignaturas_con_la_misma_fuerza_es_ambiguo(self):
        r = self.extraer("Tarea de Matemática y de Inglés")
        self.assertIsNone(r["asignatura"])
        self.assertTrue(any("varias asignaturas" in a for a in r["advertencias"]))

    def test_mencion_secundaria_baja_la_confianza_pero_no_cambia_la_eleccion(self):
        r = self.extraer("Proyecto de Ciencias Naturales sobre la lengua de los animales")
        self.assertEqual(r["asignatura_nombre"], "Ciencias Naturales")
        self.assertEqual(r["confianza"]["asignatura"], "media")
        self.assertTrue(any("También se menciona" in a for a in r["advertencias"]))

    def test_con_tilde_en_ingles(self):
        self.assertEqual(self.asignatura("Vocabulario de inglés"), "Inglés")

    def test_solo_busca_entre_las_asignaturas_del_docente(self):
        self.assertIsNone(self.asignatura("Tarea de Matemática", asignaturas=[LENGUA, INGLES]))

    def test_se_quita_la_asignatura_de_la_descripcion(self):
        r = self.extraer("Matemáticas: resolver la página 10")
        self.assertEqual(r["descripcion"], "Resolver la página 10")


class MaterialesTests(MotorBase):
    def test_lista_con_materiales_y_texto_posterior(self):
        r = self.extraer("Materiales: lápices de colores, goma y tijeras. Resolver la página 4")
        self.assertEqual(r["materiales"], ["lápices de colores", "goma", "tijeras"])
        self.assertEqual(r["descripcion"], "Resolver la página 4")

    def test_se_quitan_articulos_y_duplicados(self):
        r = self.extraer("Traer la regla, el compás y la regla")
        self.assertEqual(r["materiales"], ["regla", "compás"])

    def test_fecha_dentro_de_la_lista_no_contamina_los_materiales(self):
        r = self.extraer("Hacer un afiche y traer cartulina y marcadores para el lunes")
        self.assertEqual(r["materiales"], ["cartulina", "marcadores"])
        self.assertEqual(r["fecha_entrega"], "2026-10-05")
        self.assertEqual(r["descripcion"], "Hacer un afiche")

    def test_sin_materiales(self):
        r = self.extraer("Resolver la página 4")
        self.assertEqual(r["materiales"], [])


class TemaYBordesTests(MotorBase):
    def test_tema_explicito(self):
        r = self.extraer("Resolver ejercicios del tema fracciones equivalentes para el lunes")
        self.assertEqual(r["tema"], "Fracciones equivalentes")
        self.assertEqual(r["fecha_entrega"], "2026-10-05")

    def test_sin_tema(self):
        self.assertEqual(self.extraer("Resolver la página 4")["tema"], "")

    def test_texto_corto_conserva_la_descripcion(self):
        r = self.extraer("ok")
        self.assertEqual(r["descripcion"], "Ok")

    def test_texto_que_solo_tiene_fecha_cae_al_texto_original(self):
        r = self.extraer("Para el lunes")
        self.assertEqual(r["fecha_entrega"], "2026-10-05")
        self.assertEqual(r["confianza"]["descripcion"], "baja")
        self.assertEqual(r["descripcion"], "Para el lunes")

    def test_el_resultado_es_serializable(self):
        import json

        r = self.extraer("Para el próximo lunes realizar las páginas 20 y 21 de Matemáticas")
        json.dumps(r)

    def test_motor_informado(self):
        r_reglas = nlp.extraer("Tarea", TODAS, HOY, nlp=None)
        self.assertEqual(r_reglas["motor"], "reglas")
        pipeline = nlp.obtener_nlp()
        if pipeline is not None:
            self.assertEqual(nlp.extraer("Tarea", TODAS, HOY, nlp=pipeline)["motor"], "spacy")
