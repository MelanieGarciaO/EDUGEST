"""Los seeds leen sus datos de JSON (sin datos en el código) y validan antes de guardar."""

import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.academic.models import Asignatura, Grado, Tema

from .models import RecursoRefuerzo


class SeedsJsonTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def archivo(self, nombre, datos):
        ruta = Path(self.tmp.name) / nombre
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return str(ruta)

    def cargar_base(self):
        call_command("seed_academico", verbosity=0)
        call_command("seed_temas_ejemplo", verbosity=0)

    def test_carga_completa_desde_los_json_por_defecto(self):
        self.cargar_base()
        call_command("seed_banco_refuerzo", verbosity=0)
        self.assertEqual(Grado.objects.count(), 10)
        self.assertTrue(Tema.objects.filter(nombre="Fracciones equivalentes").exists())
        recurso = RecursoRefuerzo.objects.get(titulo="Fracciones en objetos del hogar")
        self.assertEqual((recurso.nivel, recurso.estrategia), ("BASICO", "TAREA_CASA"))

    def test_archivo_propio_de_la_institucion(self):
        ruta = self.archivo("academico.json", {"grados": [{"orden": 1, "nombre": "Primero"}], "asignaturas": ["Robótica"]})
        call_command("seed_academico", archivo=ruta, verbosity=0)
        self.assertTrue(Asignatura.objects.filter(nombre="Robótica").exists())
        self.assertFalse(Asignatura.objects.filter(nombre="Matemática").exists())

    def test_nivel_o_estrategia_invalidos_no_guardan_nada(self):
        self.cargar_base()
        ruta = self.archivo("banco.json", {"temas": [{
            "asignatura": "Matemática", "tema": "Fracciones",
            "recursos": [
                {"nivel": "BASICO", "estrategia": "INDIVIDUAL", "titulo": "Válido", "instrucciones": "x", "duracion_minutos": 10},
                {"nivel": "BASCO", "estrategia": "MAGIA", "titulo": "Con error", "instrucciones": "x", "duracion_minutos": 999},
            ],
        }]})
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_banco_refuerzo", archivo=ruta, verbosity=0)
        mensaje = str(ctx.exception)
        self.assertIn("nivel", mensaje)
        self.assertIn("estrategia", mensaje)
        self.assertIn("duracion_minutos", mensaje)
        self.assertEqual(RecursoRefuerzo.objects.count(), 0)

    def test_campo_obligatorio_vacio(self):
        ruta = self.archivo("academico.json", {"grados": [{"orden": 1, "nombre": " "}], "asignaturas": []})
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_academico", archivo=ruta, verbosity=0)
        self.assertIn("nombre", str(ctx.exception))
        self.assertEqual(Grado.objects.count(), 0)

    def test_archivo_inexistente_o_json_invalido(self):
        with self.assertRaises(CommandError):
            call_command("seed_academico", archivo="/no/existe.json", verbosity=0)
        ruta = Path(self.tmp.name) / "roto.json"
        ruta.write_text("{ no es json", encoding="utf-8")
        with self.assertRaises(CommandError) as ctx:
            call_command("seed_academico", archivo=str(ruta), verbosity=0)
        self.assertIn("JSON válido", str(ctx.exception))

    def test_grado_elegido_por_opcion(self):
        self.cargar_base()
        call_command("seed_temas_ejemplo", grado=3, verbosity=0)
        self.assertTrue(Tema.objects.filter(grado__orden=3, nombre="Fracciones").exists())

    @override_settings(GRADO_MINIMO_HABILITADO=5, GRADO_MAXIMO_HABILITADO=7)
    def test_grado_no_habilitado_se_rechaza_y_por_defecto_usa_el_maximo(self):
        call_command("seed_academico", verbosity=0)
        for fuera in (4, 8):
            with self.assertRaises(CommandError) as ctx:
                call_command("seed_temas_ejemplo", grado=fuera, verbosity=0)
            self.assertIn("no está habilitado", str(ctx.exception))
        call_command("seed_temas_ejemplo", verbosity=0)
        self.assertEqual(set(Tema.objects.values_list("grado__orden", flat=True)), {7})
