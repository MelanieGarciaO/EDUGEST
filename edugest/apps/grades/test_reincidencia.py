"""Reincidencia: una dificultad superada que vuelve a aparecer en el mismo tema."""

from .models import Dificultad
from .tests import GradesBase


class ReincidenciaTests(GradesBase):
    url = "/api/grades/dificultades/"

    def test_primera_deteccion_no_es_reincidente(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        d = Dificultad.objects.get()
        self.assertEqual((d.veces_detectada, d.reincidente), (1, False))

    def test_se_vuelve_reincidente_al_recaer_tras_superarla(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "8.0"})   # superada
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "4.5"})   # recae
        d = Dificultad.objects.get()
        self.assertEqual((d.estado, d.veces_detectada, d.reincidente), ("DETECTADA", 2, True))

    def test_actualizar_una_dificultad_vigente_no_suma_reincidencia(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "3.0"})   # sigue detectada
        self.assertEqual(Dificultad.objects.get().veces_detectada, 1)

    def test_cada_recaida_suma(self):
        for nota in ("5.0", "8.0", "4.0", "9.0", "6.0"):
            self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: nota})
        self.assertEqual(Dificultad.objects.get().veces_detectada, 3)

    def test_api_expone_y_filtra_reincidencia(self):
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "5.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "8.0"})
        self.guardar(self.doc1, self.act1, self.fracciones, {self.est1: "4.5"})
        self.guardar(self.doc1, self.act2, self.decimales, {self.est1: "5.0"})
        self.auth(self.doc1)
        res = self.client.get(self.url)
        por_tema = {d["tema"]: (d["reincidente"], d["veces_detectada"]) for d in res.data["results"]}
        self.assertEqual(por_tema, {self.fracciones.id: (True, 2), self.decimales.id: (False, 1)})
        self.assertEqual(self.client.get(self.url, {"reincidente": "true"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"reincidente": "false"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"reincidente": "x"}).status_code, 400)
