"""
Recordatorio a los representantes de las actividades que se entregan MAÑANA.

Programarlo una vez al día (por ejemplo a las 17:00):
    python manage.py enviar_recordatorios

- Solo actividades publicadas (no canceladas) de estudiantes activos.
- En modalidad «Desde la app», omite a los estudiantes que ya subieron su entrega.
- No repite: si el representante ya recibió el recordatorio de esa actividad, se omite.
- --fecha AAAA-MM-DD permite probarlo con otra fecha de entrega.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.activities.models import Actividad, ArchivoEntrega
from apps.notifications.models import Categoria, Notificacion
from apps.notifications.receivers import RUTA_ACTIVIDADES, _detalles_actividad, _entrega, _estudiantes_por_representante, _nombres
from apps.notifications.servicio import Correo, notificar


class Command(BaseCommand):
    help = "Envía recordatorios de las actividades que se entregan mañana."

    def add_arguments(self, parser):
        parser.add_argument("--fecha", help="Fecha de entrega a recordar (AAAA-MM-DD). Por defecto, mañana.")

    def handle(self, *args, fecha=None, **options):
        try:
            objetivo = date.fromisoformat(fecha) if fecha else timezone.localdate() + timedelta(days=1)
        except ValueError:
            raise CommandError("Usa el formato AAAA-MM-DD.") from None

        actividades = Actividad.objects.filter(
            estado=Actividad.Estado.PUBLICADA, fecha_entrega=objetivo
        ).select_related("asignacion__asignatura", "asignacion__paralelo__grado", "asignacion__docente")

        enviados = 0
        for a in actividades:
            entregaron = set()
            if a.modalidad_entrega == Actividad.ModalidadEntrega.APP:
                entregaron = set(ArchivoEntrega.objects.filter(actividad=a).values_list("estudiante_id", flat=True))
            ya_avisados = set(
                Notificacion.objects.filter(tipo=f"recordatorio:{a.pk}").values_list("usuario_id", flat=True)
            )
            asignatura = a.asignacion.asignatura.nombre
            for representante, estudiantes in _estudiantes_por_representante(a).items():
                faltan = [e for e in estudiantes if e.pk not in entregaron]
                if not faltan or representante.pk in ya_avisados:
                    continue
                quien = _nombres(faltan)
                notificar(
                    [representante], Categoria.RECORDATORIOS, f"recordatorio:{a.pk}",
                    titulo=f"Mañana se entrega la actividad de {asignatura}",
                    mensaje=f"Recuerda revisar la actividad de {quien}. Entrega: {_entrega(a)}.",
                    enlace=RUTA_ACTIVIDADES,
                    correo=Correo(
                        asunto=f"Recordatorio: mañana se entrega la actividad de {asignatura}",
                        parrafos=[f"Mañana vence esta actividad de {quien}:", a.descripcion],
                        detalles=_detalles_actividad(a),
                        boton=("Ver la actividad", RUTA_ACTIVIDADES),
                    ),
                    inmediato=True,  # el comando termina enseguida: no se usa hilo
                )
                enviados += 1
        self.stdout.write(self.style.SUCCESS(f"Recordatorios enviados: {enviados} (entrega {objetivo:%d/%m/%Y})."))
