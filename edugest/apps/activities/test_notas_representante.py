from datetime import timedelta
from decimal import Decimal

from django.urls import reverse

from apps.academic.models import Estudiante, Tema
from apps.grades.models import Calificacion

from .tests import HOY, ActivitiesBase


class NotasRepresentanteTests(ActivitiesBase):
    """El representante ve la nota de sus estudiantes en cada actividad."""

    def setUp(self):
        super().setUp()
        self.tema = Tema.objects.create(
            nombre="Fracciones", grado=self.par_a.grado, asignatura=self.mate
        )
        # Otro estudiante del mismo paralelo con otro representante.
        self.est3 = Estudiante.objects.create(
            first_name="Ana", last_name="Ruiz", paralelo=self.par_a, representante=self.rep2
        )
        self.actividad = self.crear_actividad(fecha=HOY - timedelta(days=1))
        for est, valor in ((self.est1, "6.50"), (self.est3, "9.00")):
            Calificacion.objects.create(
                actividad=self.actividad, estudiante=est, tema=self.tema,
                valor=Decimal(valor), registrada_por=self.doc1,
            )
        self.url = reverse("actividad-list")

    def _notas(self, res):
        return {r["id"]: r["notas"] for r in res.data["results"]}[self.actividad.id]

    def test_representante_ve_solo_la_nota_de_su_estudiante(self):
        self.auth(self.rep1)
        notas = self._notas(self.client.get(self.url))
        self.assertEqual(len(notas), 1)
        self.assertEqual(notas[0]["estudiante"], self.est1.id)
        self.assertEqual(notas[0]["valor"], "6.50")
        self.assertEqual(notas[0]["nivel"], "PROXIMO")
        self.assertEqual(notas[0]["tema_nombre"], "Fracciones")

    def test_actividad_sin_calificar_devuelve_lista_vacia(self):
        otra = self.crear_actividad(fecha=HOY - timedelta(days=2))
        self.auth(self.rep1)
        res = self.client.get(self.url)
        notas = {r["id"]: r["notas"] for r in res.data["results"]}
        self.assertEqual(notas[otra.id], [])

    def test_docente_no_recibe_el_campo_lleno(self):
        self.auth(self.doc1)
        self.assertIsNone(self._notas(self.client.get(self.url)))
