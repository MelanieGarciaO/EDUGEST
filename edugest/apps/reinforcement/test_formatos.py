"""Formato de los recursos (DUA · representación múltiple)."""

import json
from unittest import mock

from django.test import override_settings
from django.urls import reverse

from . import formatos, ia
from .models import ActividadRefuerzo, RecursoRefuerzo
from .tests import RefuerzoBase


class InferirFormatosTests(RefuerzoBase):
    def test_deduce_del_texto(self):
        casos = {
            ("Bingo de fracciones", "Juega con tu familia marcando la fracción que sale."): ["JUEGO"],
            ("Pizza de papel", "Recorta tiras de papel y compara las partes."): ["MANIPULATIVO"],
            ("Mapa de Ecuador", "Colorea las regiones en el mapa."): ["VISUAL"],
            ("Canción de los números", "Escucha la canción y repite en voz alta."): ["AUDIO"],
            ("Video del ciclo del agua", "Mira el video y responde."): ["VIDEO"],
            ("Ejercicios", "Resuelve los ejercicios de la hoja."): ["TEXTO"],
            ("Repaso", "Repasa el tema."): ["TEXTO"],  # sin pistas: texto
        }
        for (titulo, instrucciones), esperado in casos.items():
            self.assertEqual(formatos.inferir(titulo, instrucciones), esperado, titulo)
        # Varios canales a la vez, en el orden del catálogo y con un máximo.
        varios = formatos.inferir("Juego con dados", "Dibuja y lee la ficha; mira el video.")
        self.assertEqual(varios, ["TEXTO", "VISUAL", "VIDEO", "JUEGO"])

    def test_limpiar(self):
        self.assertEqual(formatos.limpiar(["juego", "TEXTO", "JUEGO", "nada"]), ["TEXTO", "JUEGO"])
        self.assertEqual(formatos.limpiar(None), [])

    def test_se_deduce_al_guardar_si_no_se_indica(self):
        r = RecursoRefuerzo.objects.create(
            tema=self.fracciones, nivel="BASICO", titulo="Dominó de fracciones", instrucciones="Juega dominó."
        )
        self.assertEqual(r.formatos, ["JUEGO"])
        indicado = RecursoRefuerzo.objects.create(
            tema=self.fracciones, nivel="BASICO", titulo="Otro", instrucciones="Juega.", formatos=["VIDEO"]
        )
        self.assertEqual(indicado.formatos, ["VIDEO"])

    def test_completar_existentes(self):
        RecursoRefuerzo.objects.filter(pk=self.b1.pk).update(formatos=[], titulo="Rompecabezas")
        formatos.completar_existentes(RecursoRefuerzo, ActividadRefuerzo)
        self.b1.refresh_from_db()
        self.assertEqual(self.b1.formatos, ["JUEGO"])


class BancoFormatosApiTests(RefuerzoBase):
    def crear(self, **extra):
        self.auth(self.doc1)
        datos = {"tema": self.fracciones.id, "nivel": "BASICO", "titulo": "Feria de fracciones",
                 "instrucciones": "Arma una tienda con precios en fracciones.", **extra}
        return self.client.post(reverse("recurso-list"), datos, format="json")

    def test_crear_con_formatos(self):
        res = self.crear(formatos=["JUEGO", "MANIPULATIVO", "JUEGO"])
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["formatos"], ["MANIPULATIVO", "JUEGO"])

    def test_crear_sin_formatos_los_deduce(self):
        res = self.crear(instrucciones="Mira el video y dibuja lo que entendiste.")
        self.assertEqual(res.data["formatos"], ["VISUAL", "VIDEO"])

    def test_validaciones(self):
        self.assertEqual(self.crear(formatos=["HOLOGRAMA"]).status_code, 400)
        self.assertEqual(self.crear(formatos=list(formatos.FormatoRecurso.values)).status_code, 400)  # máx. 4
        recurso = self.crear(formatos=["JUEGO"]).data["id"]
        url = reverse("recurso-detail", args=[recurso])
        res = self.client.patch(url, {"formatos": []}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("al menos un formato", str(res.data["formatos"]))
        self.assertEqual(self.client.patch(url, {"formatos": ["VIDEO"]}, format="json").data["formatos"], ["VIDEO"])

    def test_filtrar_por_formato(self):
        RecursoRefuerzo.objects.filter(pk=self.b2.pk).update(formatos=["JUEGO", "VISUAL"])
        self.auth(self.doc1)
        res = self.client.get(reverse("recurso-list"), {"formato": "JUEGO", "tema": self.fracciones.id})
        self.assertEqual([r["id"] for r in res.data["results"]], [self.b2.id])
        self.assertEqual(self.client.get(reverse("recurso-list"), {"formato": "X"}).status_code, 400)


class PlanFormatosTests(RefuerzoBase):
    def test_prefiere_formatos_distintos(self):
        # Básicas: b1 y b2 son texto; b3 es un juego. ALTA pide 2 básicas: b1 y luego b3 (formato nuevo).
        RecursoRefuerzo.objects.filter(pk=self.b3.pk).update(formatos=["JUEGO"])
        tema = self.plan_con({self.fracciones: 3})["temas"][0]
        del_banco = [a for a in tema["actividades"] if a["origen"] == "BANCO" and a["nivel"] == "BASICO"]
        self.assertEqual({a["recurso"] for a in del_banco}, {self.b1.id, self.b3.id})
        juego = next(a for a in del_banco if a["recurso"] == self.b3.id)
        self.assertEqual(juego["formatos"], ["JUEGO"])  # se copia a la actividad del plan

    def test_no_recibido_antes_que_formato_nuevo(self):
        # Si el formato nuevo ya lo recibió, manda lo que aún no recibe (regla anterior).
        RecursoRefuerzo.objects.filter(pk=self.b3.pk).update(formatos=["JUEGO"])
        from . import services

        elegidos = services._seleccionar_recursos(self.fracciones, "ALTA", {self.b3.id})
        self.assertEqual([r.id for r in elegidos if r.nivel == "BASICO"], [self.b1.id, self.b2.id])

    def test_actividad_propia_y_edicion(self):
        plan = self.plan_con({self.fracciones: 6})
        tema_id = plan["temas"][0]["id"]
        self.auth(self.doc1)
        res = self.client.post(reverse("tema-plan-agregar-actividad", args=[tema_id]), {
            "titulo": "Lotería de fracciones", "instrucciones": "Juega lotería con tu familia.",
        }, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["formatos"], ["JUEGO"])
        url = reverse("actividad-refuerzo-detail", args=[res.data["id"]])
        self.assertEqual(self.client.patch(url, {"formatos": ["AUDIO"]}, format="json").data["formatos"], ["AUDIO"])
        self.assertEqual(self.client.patch(url, {"formatos": []}, format="json").status_code, 400)


@override_settings(GEMINI_API_KEY="clave-de-prueba")
class IAFormatosTests(RefuerzoBase):
    def pedir(self, recursos):
        with mock.patch.object(ia, "_llamar_modelo", return_value=(json.dumps({"recursos": recursos}), "m")):
            self.auth(self.doc1)
            return self.client.post(reverse("recurso-generar-ia"), {
                "tema": self.fracciones.id, "nivel": "BASICO", "cantidad": 2,
            }, format="json")

    def test_la_ia_propone_formatos_y_si_faltan_se_deducen(self):
        base = {"instrucciones": "1. Recorta tiras de papel.\n2. Compara las partes iguales.\n3. Explica.",
                "estrategia": "INDIVIDUAL", "duracion_minutos": 20, "fase": "EXPERIENCIA"}
        res = self.pedir([
            {**base, "titulo": "Tiras de fracciones", "formatos": ["manipulativo", "VISUAL", "INVENTADO"]},
            {**base, "titulo": "Comparo partes iguales"},  # sin formatos
        ])
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([p["formatos"] for p in res.data["propuestas"]], [["VISUAL", "MANIPULATIVO"], ["MANIPULATIVO"]])
        self.assertIn("formatos", ia.esquema(None)["properties"]["recursos"]["items"]["required"])
