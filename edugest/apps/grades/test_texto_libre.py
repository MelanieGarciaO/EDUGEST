"""Mejora 13: notas desde texto libre («Vera 9, Pérez 4,5»)."""

from django.urls import reverse

from apps.academic.models import Estudiante

from .models import Calificacion
from .tests import GradesBase


class TextoLibreTests(GradesBase):
    def interpretar(self, texto, user=None):
        self.auth(user or self.doc1)
        return self.client.post(
            reverse("actividad-calificaciones-texto", args=[self.act1.id]), {"texto": texto}, format="json"
        )

    def test_lista_en_una_linea(self):
        res = self.interpretar("Pérez 9, Vera 4,5")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(
            [(f["estudiante"], f["valor"]) for f in res.data["filas"]],
            [(self.est1.id, "9.00"), (self.est3.id, "4.50")],
        )
        self.assertFalse(Calificacion.objects.exists())  # solo vista previa

    def test_una_por_linea_con_separadores_y_tildes(self):
        res = self.interpretar("luis perez: 8.75\nMarta Vera = 10")
        self.assertEqual([f["valor"] for f in res.data["filas"]], ["8.75", "10.00"])

    def test_tipeo_leve_da_confianza_media(self):
        res = self.interpretar("Peres 7")
        self.assertEqual((res.data["filas"][0]["estudiante"], res.data["filas"][0]["confianza"]), (self.est1.id, "media"))

    def test_apellido_compartido_es_ambiguo(self):
        Estudiante.objects.create(first_name="Ana", last_name="Pérez", paralelo=self.par_a, representante=self.rep1)
        res = self.interpretar("Pérez 8, Luis Pérez 9")
        self.assertEqual([f["estudiante"] for f in res.data["filas"]], [self.est1.id])
        self.assertIn("escribe el nombre completo", res.data["errores"][0]["mensaje"])

    def test_otro_paralelo_nota_fuera_de_rango_y_repetidos(self):
        res = self.interpretar("Mora 8, Vera 11, Pérez 6, Luis 7")
        mensajes = " | ".join(e["mensaje"] for e in res.data["errores"])
        self.assertIn("no coincide", mensajes)          # Sofía Mora es del paralelo B
        self.assertIn("entre 0 y 10", mensajes)
        self.assertIn("ya tenía nota", mensajes)
        self.assertEqual([f["estudiante"] for f in res.data["filas"]], [self.est1.id])

    def test_texto_vacio_o_sin_notas(self):
        self.assertEqual(self.interpretar("").status_code, 400)
        self.assertEqual(self.interpretar("hola a todos").status_code, 400)

    def test_solo_docente_de_la_actividad(self):
        self.assertEqual(self.interpretar("Pérez 9", user=self.doc2).status_code, 404)
        self.assertEqual(self.interpretar("Pérez 9", user=self.rep1).status_code, 403)
