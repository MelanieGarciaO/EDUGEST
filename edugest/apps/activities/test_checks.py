"""Comprobación de arranque: aviso cuando falta el modelo de spaCy."""

from unittest import mock

from django.test import SimpleTestCase, override_settings

from .checks import modelo_spacy_instalado


class ModeloSpacyCheckTests(SimpleTestCase):
    def test_sin_aviso_si_el_modelo_esta_instalado(self):
        with mock.patch("importlib.util.find_spec", return_value=object()):
            self.assertEqual(modelo_spacy_instalado(None), [])

    def test_avisa_si_falta_el_modelo(self):
        def find_spec(nombre):
            return object() if nombre == "spacy" else None

        with mock.patch("importlib.util.find_spec", side_effect=find_spec):
            avisos = modelo_spacy_instalado(None)
        self.assertEqual([a.id for a in avisos], ["edugest.W001"])
        self.assertIn("es_core_news_sm", avisos[0].msg)

    def test_avisa_si_falta_spacy(self):
        with mock.patch("importlib.util.find_spec", return_value=None):
            avisos = modelo_spacy_instalado(None)
        self.assertIn("«spacy»", avisos[0].msg)

    @override_settings(PLN_SPACY_MODEL="")
    def test_sin_aviso_si_el_pln_con_spacy_esta_desactivado(self):
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertEqual(modelo_spacy_instalado(None), [])
