"""Observación (retroalimentación) opcional del docente al registrar una nota."""

from django.urls import reverse

from .models import Calificacion, CalificacionHistorial
from .tests import GradesBase


class ObservacionTests(GradesBase):
    def enviar(self, items, user=None, tema=None):
        self.auth(user or self.doc1)
        cuerpo = {"tema": (tema or self.fracciones).id, "calificaciones": items}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.url_notas(self.act1), cuerpo, format="json")

    def nota(self, estudiante=None):
        return Calificacion.objects.get(actividad=self.act1, estudiante=estudiante or self.est1)

    def test_es_opcional(self):
        res = self.enviar([{"estudiante": self.est1.id, "valor": "8"}])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.nota().observacion, "")
        self.assertEqual(res.data["calificaciones"][0]["observacion"], "")

    def test_se_guarda_con_la_nota_y_se_recorta(self):
        res = self.enviar([
            {"estudiante": self.est1.id, "valor": "6", "observacion": "  Repasa la suma de fracciones.  "},
            {"estudiante": self.est3.id, "valor": "9.5"},
        ])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.nota().observacion, "Repasa la suma de fracciones.")
        self.assertEqual(self.nota(self.est3).observacion, "")

    def test_cambiar_solo_la_observacion(self):
        self.enviar([{"estudiante": self.est1.id, "valor": "6"}])
        eventos = len(self.eventos)
        res = self.enviar([{"estudiante": self.est1.id, "valor": "6", "observacion": "Mejoró la presentación."}])
        self.assertEqual((res.data["creadas"], res.data["actualizadas"], res.data["sin_cambios"]), (0, 1, 0))
        self.assertEqual(self.nota().observacion, "Mejoró la presentación.")
        # No es una corrección de la nota: sin historial ni recálculo de dificultades.
        self.assertFalse(CalificacionHistorial.objects.exists())
        self.assertEqual(len(self.eventos), eventos)

    def test_no_enviarla_la_conserva_y_vacia_la_borra(self):
        self.enviar([{"estudiante": self.est1.id, "valor": "6", "observacion": "Buen esfuerzo."}])
        res = self.enviar([{"estudiante": self.est1.id, "valor": "6"}])
        self.assertEqual(res.data["sin_cambios"], 1)
        self.assertEqual(self.nota().observacion, "Buen esfuerzo.")
        # Corregir la nota sin enviar observación tampoco la borra.
        self.enviar([{"estudiante": self.est1.id, "valor": "7"}])
        self.assertEqual(self.nota().observacion, "Buen esfuerzo.")
        self.enviar([{"estudiante": self.est1.id, "valor": "7", "observacion": ""}])
        self.assertEqual(self.nota().observacion, "")

    def test_maximo_500_caracteres(self):
        res = self.enviar([{"estudiante": self.est1.id, "valor": "6", "observacion": "a" * 501}])
        self.assertEqual(res.status_code, 400)
        self.assertFalse(Calificacion.objects.exists())
        res = self.enviar([{"estudiante": self.est1.id, "valor": "6", "observacion": "a" * 500}])
        self.assertEqual(res.status_code, 200)

    def test_el_docente_la_ve_al_volver_a_calificar(self):
        self.enviar([{"estudiante": self.est1.id, "valor": "6", "observacion": "Practica en casa."}])
        filas = {f["estudiante"]: f for f in self.client.get(self.url_notas(self.act1)).data["calificaciones"]}
        self.assertEqual(filas[self.est1.id]["observacion"], "Practica en casa.")
        self.assertEqual(filas[self.est3.id]["observacion"], "")

    def test_el_representante_ve_solo_la_de_su_estudiante(self):
        self.enviar([
            {"estudiante": self.est1.id, "valor": "6", "observacion": "Para Luis"},
            {"estudiante": self.est3.id, "valor": "9", "observacion": "Para Marta"},
        ])
        self.auth(self.rep1)
        res = self.client.get(reverse("actividad-detail", args=[self.act1.id]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual([(n["estudiante_nombre"], n["observacion"]) for n in res.data["notas"]], [("Luis Pérez", "Para Luis")])
