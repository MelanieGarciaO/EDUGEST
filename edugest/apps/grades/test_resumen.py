"""Mejora 8: resumen del desempeño en lenguaje claro para la familia."""

from django.urls import reverse

from .tests import GradesBase


class ResumenClaroTests(GradesBase):
    def resumen(self, user=None, estudiante=None):
        self.auth(user or self.rep1)
        res = self.client.get(reverse("desempeno-estudiante", args=[(estudiante or self.est1).id]))
        self.assertEqual(res.status_code, 200, res.data)
        return res.data["resumen"]

    def test_sin_notas_no_hay_resumen(self):
        self.assertIsNone(self.resumen())

    def test_buen_desempeno_y_fortalezas(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "9.5"})
        r = self.resumen()
        self.assertIn("Luis tiene un desempeño excelente", r["general"])
        self.assertIn("9,50", r["general"])
        self.assertEqual(r["asignaturas"], ["En Matemática tiene un desempeño excelente."])
        self.assertEqual(r["fortalezas"], "Domina muy bien: Fracciones.")
        self.assertEqual(r["a_reforzar"], [])
        self.assertIn("Siga motivando a Luis", r["recomendacion"])

    def test_dificultad_y_recomendacion(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5"})
        r = self.resumen()
        self.assertIn("está cerca de lograr lo esperado", r["general"])
        self.assertEqual(len(r["a_reforzar"]), 1)
        self.assertIn("Fracciones (Matemática): le falta poco", r["a_reforzar"][0])
        self.assertIn("Planes de refuerzo", r["recomendacion"])

    def test_reincidencia_y_superados(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "8"})
        r = self.resumen()
        self.assertEqual(r["superados"], "Superó las dificultades que tenía en: Fracciones.")
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "4"})
        r = self.resumen()
        self.assertIn("volvió a tener dificultad", r["a_reforzar"][0])

    def test_sin_siglas_tecnicas(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "3"})
        texto = str(self.resumen())
        for sigla in ("NAAR", "PAAR", "AAR", "DAR", "DETECTADA", "ALTA"):
            self.assertNotIn(sigla, texto)
