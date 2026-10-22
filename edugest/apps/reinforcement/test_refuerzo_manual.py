"""Refuerzo manual por tema (sin dificultad detectada) y estrategias de refuerzo."""

from django.urls import reverse

from .models import ActividadRefuerzo, EstrategiaRefuerzo, RecursoRefuerzo
from .tests import RefuerzoBase


class RefuerzoManualTests(RefuerzoBase):
    def generar_manual(self, temas, estudiante=None, user=None):
        self.auth(user or self.doc1)
        return self.post(
            reverse("plan-generar"),
            {
                "estudiante": (estudiante or self.est1).id,
                "asignatura": self.mate.id,
                "temas_manuales": temas,
            },
        )

    def test_sin_dificultades_y_sin_temas_manuales_se_rechaza(self):
        res = self.generar()
        self.assertEqual(res.status_code, 400)
        self.assertIn("refuerzo de un tema concreto", str(res.data))

    def test_plan_solo_con_tema_manual_aunque_promedie_mas_de_7(self):
        self.dar_nota(self.est1, self.fracciones, 8.5)
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "Falla al comparar fracciones"}])
        self.assertEqual(res.status_code, 201, res.data)
        tema = res.data["temas"][0]
        self.assertEqual(tema["origen"], "MANUAL")
        self.assertEqual(tema["nivel_dificultad"], "MANUAL")
        self.assertEqual(tema["promedio_inicial"], "8.50")
        self.assertIsNone(tema["dificultad_estado"])
        self.assertIn("Falla al comparar fracciones", tema["objetivo"])
        # carga ligera: 1 básica + 2 intermedias
        niveles = [a["nivel"] for a in tema["actividades"]]
        self.assertEqual(niveles, ["BASICO", "INTERMEDIO", "INTERMEDIO"])
        self.assertEqual(res.data["nivel"], "REGULAR")

    def test_tema_manual_sin_notas_tiene_promedio_nulo(self):
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "Refuerzo preventivo"}])
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["temas"][0]["promedio_inicial"])

    def test_manual_y_dificultades_se_combinan_con_prioridad_manual(self):
        self.dar_nota(self.est1, self.decimales, 3.0)
        self.dar_nota(self.est1, self.proporcion, 5.0)
        self.dar_nota(self.est1, self.fracciones, 9.0)
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "Una destreza"}])
        self.assertEqual(res.status_code, 201, res.data)
        origenes = [(t["tema_nombre"], t["origen"]) for t in res.data["temas"]]
        self.assertEqual(origenes[0], ("Fracciones", "MANUAL"))
        self.assertEqual(len(origenes), 3)
        self.assertEqual(res.data["nivel"], "ALTO")  # Decimales (3,0) es dificultad alta

    def test_maximo_tres_temas_con_los_manuales(self):
        for t in (self.decimales, self.proporcion):
            self.dar_nota(self.est1, t, 5.0)
        extra = self.equivalentes
        res = self.generar_manual(
            [
                {"tema": self.fracciones.id, "motivo": "a"},
                {"tema": extra.id, "motivo": "b"},
            ]
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(len(res.data["temas"]), 3)  # 2 manuales + 1 dificultad

    def test_tema_con_dificultad_detectada_no_puede_pedirse_a_mano(self):
        self.dar_nota(self.est1, self.fracciones, 5.0)
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "x"}])
        self.assertEqual(res.status_code, 400)
        self.assertIn("ya tiene una dificultad detectada", str(res.data))

    def test_tema_de_otra_asignatura_se_rechaza(self):
        res = self.generar_manual([{"tema": self.comprension.id, "motivo": "x"}])
        self.assertEqual(res.status_code, 400)

    def test_tema_repetido_se_rechaza(self):
        res = self.generar_manual(
            [{"tema": self.fracciones.id, "motivo": "a"}, {"tema": self.fracciones.id, "motivo": "b"}]
        )
        self.assertEqual(res.status_code, 400)

    def test_motivo_es_obligatorio(self):
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": ""}])
        self.assertEqual(res.status_code, 400)

    def test_mas_de_tres_temas_manuales_se_rechaza(self):
        res = self.generar_manual(
            [{"tema": t.id, "motivo": "x"} for t in (self.fracciones, self.equivalentes, self.decimales, self.proporcion)]
        )
        self.assertEqual(res.status_code, 400)

    def test_tema_manual_cuenta_como_superado_al_cumplir_todas_sus_actividades(self):
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "x"}])
        plan_id = res.data["id"]
        self.post(reverse("plan-aprobar", args=[plan_id]))
        self.auth(self.rep1)
        for act in res.data["temas"][0]["actividades"]:
            self.post(reverse("actividad-refuerzo-cumplir", args=[act["id"]]))
        plan = self.client.get(reverse("plan-detail", args=[plan_id])).data
        self.assertEqual(plan["avance"]["temas_superados"], 1)
        self.assertEqual(plan["estado"], "COMPLETADA")

    def test_representante_no_puede_pedir_refuerzo_manual(self):
        res = self.generar_manual([{"tema": self.fracciones.id, "motivo": "x"}], user=self.rep1)
        self.assertEqual(res.status_code, 403)


class EstrategiaTests(RefuerzoBase):
    def test_recurso_sin_estrategia_usa_individual(self):
        self.assertEqual(self.b1.estrategia, EstrategiaRefuerzo.INDIVIDUAL)

    def test_docente_crea_recurso_con_estrategia(self):
        self.auth(self.doc1)
        res = self.client.post(
            reverse("recurso-list"),
            {"tema": self.fracciones.id, "nivel": "BASICO", "titulo": "Juego en parejas",
             "instrucciones": "Jueguen.", "estrategia": "ENTRE_IGUALES"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["estrategia"], "ENTRE_IGUALES")

    def test_estrategia_invalida_se_rechaza(self):
        self.auth(self.doc1)
        res = self.client.post(
            reverse("recurso-list"),
            {"tema": self.fracciones.id, "nivel": "BASICO", "titulo": "X", "instrucciones": "Y", "estrategia": "MAGIA"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_filtro_por_estrategia(self):
        RecursoRefuerzo.objects.filter(pk=self.b1.pk).update(estrategia="TECNOLOGIA")
        self.auth(self.doc1)
        res = self.client.get(reverse("recurso-list"), {"estrategia": "tecnologia"})
        ids = [r["id"] for r in (res.data["results"] if "results" in res.data else res.data)]
        self.assertEqual(ids, [self.b1.id])
        self.assertEqual(self.client.get(reverse("recurso-list"), {"estrategia": "x"}).status_code, 400)

    def test_el_plan_copia_la_estrategia_del_recurso(self):
        RecursoRefuerzo.objects.filter(pk=self.b1.pk).update(estrategia="TAREA_CASA")
        plan = self.plan_con({self.fracciones: 5.0})
        estrategias = {a["titulo"]: a["estrategia"] for a in plan["temas"][0]["actividades"]}
        self.assertEqual(estrategias.get("Básica 1"), "TAREA_CASA")

    def test_actividad_propia_con_estrategia_y_edicion(self):
        plan = self.plan_con({self.fracciones: 5.0})
        self.auth(self.doc1)
        tema_plan_id = plan["temas"][0]["id"]
        res = self.post(
            reverse("tema-plan-agregar-actividad", args=[tema_plan_id]),
            {"titulo": "Cuaderno compartido", "instrucciones": "Hazlo", "estrategia": "COOPERATIVO"},
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["estrategia"], "COOPERATIVO")
        res2 = self.patch(reverse("actividad-refuerzo-detail", args=[res.data["id"]]), {"estrategia": "GRUPAL"})
        self.assertEqual(res2.status_code, 200, res2.data)
        self.assertEqual(ActividadRefuerzo.objects.get(pk=res.data["id"]).estrategia, "GRUPAL")
