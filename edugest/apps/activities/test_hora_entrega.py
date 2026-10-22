"""Hora de entrega opcional: 00:00 (por defecto) significa sin hora, la entrega vale todo el día."""

from datetime import time
from unittest.mock import patch

from .models import SIN_HORA, Actividad
from .tests import HOY, MANANA, ActivitiesBase

URL = "/api/activities/actividades/"


class HoraEntregaTests(ActivitiesBase):
    def setUp(self):
        super().setUp()
        p = patch("apps.activities.clock.hora_actual", return_value=time(10, 0))
        p.start()
        self.addCleanup(p.stop)
        self.auth(self.doc1)

    def payload(self, **cambios):
        datos = {
            "paralelo": self.par_a.id,
            "asignatura": self.mate.id,
            "descripcion": "Realizar las páginas 20 y 21",
            "fecha_entrega": MANANA.isoformat(),
        }
        datos.update(cambios)
        return datos

    def publicar(self, formato="json", **cambios):
        return self.client.post(URL, self.payload(**cambios), format=formato)

    def test_sin_hora_queda_en_cero(self):
        res = self.publicar()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["hora_entrega"], "00:00:00")

    def test_hora_nula_o_vacia_equivale_a_sin_hora(self):
        for formato, valor in (("json", None), ("multipart", "")):
            res = self.publicar(formato=formato, hora_entrega=valor)
            self.assertEqual(res.status_code, 201, res.data)
            self.assertEqual(res.data["hora_entrega"], "00:00:00")

    def test_publicar_con_hora(self):
        res = self.publicar(hora_entrega="14:30")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["hora_entrega"], "14:30:00")
        self.assertEqual(res.data["vigencia"], "pendiente")

    def test_hora_invalida(self):
        self.assertEqual(self.publicar(hora_entrega="25:99").status_code, 400)

    def test_hoy_con_hora_futura_es_valido(self):
        res = self.publicar(fecha_entrega=HOY.isoformat(), hora_entrega="15:00")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["vigencia"], "pendiente")

    def test_hoy_con_hora_pasada_se_rechaza(self):
        res = self.publicar(fecha_entrega=HOY.isoformat(), hora_entrega="09:00")
        self.assertEqual(res.status_code, 400)
        self.assertIn("hora_entrega", res.data)

    def test_hoy_sin_hora_sigue_valido_todo_el_dia(self):
        res = self.publicar(fecha_entrega=HOY.isoformat())
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["vigencia"], "pendiente")

    def test_vigencia_segun_la_hora(self):
        antes = self.crear_actividad(fecha=HOY, hora_entrega=time(9, 0))   # ya pasó (son las 10:00)
        despues = self.crear_actividad(fecha=HOY, hora_entrega=time(11, 0))  # todavía no
        todo_el_dia = self.crear_actividad(fecha=HOY)
        self.assertEqual(antes.vigencia(), "finalizada")
        self.assertEqual(despues.vigencia(), "pendiente")
        self.assertEqual(todo_el_dia.vigencia(), "pendiente")

    def test_filtros_pendiente_y_finalizada_consideran_la_hora(self):
        antes = self.crear_actividad(fecha=HOY, hora_entrega=time(9, 0))
        despues = self.crear_actividad(fecha=HOY, hora_entrega=time(11, 0))
        todo_el_dia = self.crear_actividad(fecha=HOY)
        ids = lambda v: sorted(i["id"] for i in self.client.get(URL, {"vigencia": v}).data["results"])
        self.assertEqual(ids("finalizada"), [antes.id])
        self.assertEqual(ids("pendiente"), sorted([despues.id, todo_el_dia.id]))

    def test_no_se_edita_una_actividad_con_la_hora_vencida(self):
        act = self.crear_actividad(fecha=HOY, hora_entrega=time(9, 0))
        res = self.client.patch(f"{URL}{act.id}/", {"descripcion": "Otra"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_editar_la_hora_y_notificar_el_cambio(self):
        act = self.crear_actividad(fecha=MANANA)
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.patch(f"{URL}{act.id}/", {"hora_entrega": "08:15"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["hora_entrega"], "08:15:00")
        self.assertEqual(self.eventos, [("modificada", act.pk, ["hora_entrega"])])

    def test_quitar_la_hora_al_editar(self):
        act = self.crear_actividad(fecha=MANANA, hora_entrega=time(8, 0))
        res = self.client.patch(f"{URL}{act.id}/", {"hora_entrega": None}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        act.refresh_from_db()
        self.assertEqual(act.hora_entrega, SIN_HORA)

    def test_editar_la_fecha_a_hoy_con_hora_pasada_se_rechaza(self):
        act = self.crear_actividad(fecha=MANANA, hora_entrega=time(9, 0))
        res = self.client.patch(f"{URL}{act.id}/", {"fecha_entrega": HOY.isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("hora_entrega", res.data)

    def test_listado_ordena_por_fecha_y_hora(self):
        tarde = self.crear_actividad(fecha=MANANA, hora_entrega=time(16, 0))
        temprano = self.crear_actividad(fecha=MANANA, hora_entrega=time(8, 0))
        res = self.client.get(URL, {"vigencia": "pendiente"})
        ids = [i["id"] for i in res.data["results"] if i["id"] in (tarde.id, temprano.id)]
        self.assertEqual(ids[0], temprano.id)  # 08:00 antes que 16:00 (00:00 se trata aparte)
        self.assertIsInstance(Actividad.objects.get(pk=tarde.id).hora_entrega, time)
