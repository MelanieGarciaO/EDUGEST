"""Acuse de recibo: el representante confirma que revisó el plan con el estudiante."""

from django.urls import reverse

from .models import PlanRefuerzo
from .tests import RefuerzoBase


class AcuseReciboTests(RefuerzoBase):
    def setUp(self):
        super().setUp()
        self.plan = self.plan_con({self.fracciones: "3.5"})
        self.url = reverse("plan-revisar", args=[self.plan["id"]])

    def aprobar(self):
        self.auth(self.doc1)
        self.post(reverse("plan-aprobar", args=[self.plan["id"]]))

    def test_representante_confirma_la_revision(self):
        self.aprobar()
        self.auth(self.rep1)
        res = self.post(self.url)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIsNotNone(res.data["revisado_en"])
        self.assertEqual(res.data["revisado_por_nombre"], self.rep1.full_name)

    def test_es_idempotente_y_conserva_la_primera_fecha(self):
        self.aprobar()
        self.auth(self.rep1)
        primera = self.post(self.url).data["revisado_en"]
        self.assertEqual(self.post(self.url).data["revisado_en"], primera)

    def test_el_docente_ve_el_acuse(self):
        self.aprobar()
        self.auth(self.rep1)
        self.post(self.url)
        self.auth(self.doc1)
        res = self.client.get(f"/api/reinforcement/planes/{self.plan['id']}/")
        self.assertIsNotNone(res.data["revisado_en"])

    def test_plan_en_propuesta_no_se_puede_confirmar(self):
        plan = PlanRefuerzo.objects.get(pk=self.plan["id"])
        self.auth(self.rep1)
        res = self.post(self.url)
        # La propuesta aún no es visible para la familia: 404 o 400, nunca se marca.
        self.assertIn(res.status_code, (400, 404))
        plan.refresh_from_db()
        self.assertIsNone(plan.revisado_en)

    def test_solo_el_representante_del_estudiante(self):
        self.aprobar()
        self.auth(self.rep2)   # representa a otros estudiantes
        self.assertEqual(self.post(self.url).status_code, 404)

    def test_docente_no_puede_marcar_el_acuse(self):
        self.aprobar()
        self.auth(self.doc1)
        self.assertEqual(self.post(self.url).status_code, 403)
