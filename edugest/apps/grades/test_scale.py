from decimal import Decimal

from django.test import SimpleTestCase

from . import scale


def d(valor):
    return Decimal(valor)


class NivelCualitativoTests(SimpleTestCase):
    def test_limites_de_la_escala(self):
        casos = {
            "10": scale.DOMINA,
            "9.00": scale.DOMINA,
            "8.99": scale.ALCANZA,
            "7.00": scale.ALCANZA,
            "6.99": scale.PROXIMO,
            "4.01": scale.PROXIMO,
            "4.00": scale.NO_ALCANZA,
            "0": scale.NO_ALCANZA,
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(scale.nivel_cualitativo(d(valor)), esperado)

    def test_sin_valor(self):
        self.assertIsNone(scale.nivel_cualitativo(None))
        self.assertIsNone(scale.nombre_nivel(None))

    def test_nombres(self):
        self.assertEqual(scale.nombre_nivel(scale.PROXIMO), "Está próximo a alcanzar los aprendizajes")


class DificultadTests(SimpleTestCase):
    def test_umbral_de_siete(self):
        self.assertIsNone(scale.nivel_dificultad(d("7.00")))
        self.assertIsNone(scale.nivel_dificultad(d("10")))
        self.assertEqual(scale.nivel_dificultad(d("6.99")), scale.MODERADA)
        self.assertEqual(scale.nivel_dificultad(d("4.01")), scale.MODERADA)
        self.assertEqual(scale.nivel_dificultad(d("4.00")), scale.ALTA)
        self.assertEqual(scale.nivel_dificultad(d("0")), scale.ALTA)

    def test_sin_promedio(self):
        self.assertIsNone(scale.nivel_dificultad(None))


class PromedioTests(SimpleTestCase):
    def test_media_simple(self):
        self.assertEqual(scale.promedio([d("6.0"), d("7.5")]), d("6.75"))

    def test_redondeo_mitad_hacia_arriba(self):
        # 6.995 se redondea a 7.00 y, por lo tanto, ya no es dificultad.
        self.assertEqual(scale.promedio([d("6.99"), d("7.00"), d("7.00"), d("7.00")]), d("7.00"))
        self.assertEqual(scale.promedio([d("7"), d("6.99")]), d("7.00"))
        self.assertIsNone(scale.nivel_dificultad(scale.promedio([d("7"), d("6.99")])))

    def test_sin_valores(self):
        self.assertIsNone(scale.promedio([]))

    def test_un_solo_valor(self):
        self.assertEqual(scale.promedio([d("3.5")]), d("3.50"))
