"""Mejora 10: tablero de alerta temprana institucional."""

from django.test import override_settings
from django.urls import reverse

from .tests import RefuerzoBase


@override_settings(GRADO_MINIMO_HABILITADO=1, GRADO_MAXIMO_HABILITADO=10)
class AlertaTempranaTests(RefuerzoBase):
    url = reverse("alerta-temprana")

    def tablero(self):
        self.auth(self.admin)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def test_sin_datos(self):
        t = self.tablero()
        self.assertEqual(t["resumen"]["con_dificultad"], 0)
        self.assertEqual(t["asignaturas_en_refuerzo"], [])
        self.assertEqual(t["paralelos_menor_rendimiento"], [])
        self.assertEqual(t["temas_mayor_dificultad"], [])

    def test_indicadores(self):
        self.dar_nota(self.est1, self.fracciones, "4")    # A: dificultad
        self.dar_nota(self.est3, self.fracciones, "9")    # A: sin dificultad
        self.dar_nota(self.est2, self.fracciones, "5")    # B: dificultad
        self.dar_nota(self.est1, self.comprension, "6")   # A: dificultad en Lengua
        t = self.tablero()

        r = t["resumen"]
        self.assertEqual((r["estudiantes"], r["con_dificultad"]), (3, 2))
        self.assertEqual(r["porcentaje_con_dificultad"], 66.7)

        asignaturas = {a["nombre"]: a["estudiantes"] for a in t["asignaturas_en_refuerzo"]}
        self.assertEqual(asignaturas, {"Matemática": 2, "Lengua y Literatura": 1})
        self.assertEqual(t["asignaturas_en_refuerzo"][0]["nombre"], "Matemática")

        # Paralelo B (5,00) rinde menos que A (promedio de 4, 9 y 6 = 6,33).
        paralelos = [(p["nombre"], p["promedio"], p["nivel"]) for p in t["paralelos_menor_rendimiento"]]
        self.assertEqual(paralelos, [("Séptimo EGB B", "5.00", "PROXIMO"), ("Séptimo EGB A", "6.33", "PROXIMO")])

        temas = {x["nombre"]: (x["con_dificultad"], x["calificados"], x["indice"]) for x in t["temas_mayor_dificultad"]}
        self.assertEqual(temas["Comprensión lectora"], (1, 1, 100.0))
        self.assertEqual(temas["Fracciones"], (2, 3, 66.7))
        self.assertEqual(t["temas_mayor_dificultad"][0]["nombre"], "Comprensión lectora")

    def test_reincidentes(self):
        # Cada nota es una actividad nueva: el promedio sube a 8 (superada) y luego baja.
        for nota in ("4", "10", "10", "0"):
            self.dar_nota(self.est1, self.fracciones, nota)
        t = self.tablero()
        self.assertEqual(t["resumen"]["reincidentes"], 1)
        self.assertEqual(t["temas_mayor_dificultad"][0]["reincidentes"], 1)

    def test_solo_administrador(self):
        for user in (self.doc1, self.rep1):
            self.auth(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
