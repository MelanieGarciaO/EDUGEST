"""
Suscripciones del módulo de refuerzo a eventos de otros módulos (se conectan en apps.ready).
"""

from django.dispatch import receiver

from apps.grades.models import Calificacion
from apps.grades.signals import calificaciones_guardadas

from . import services


@receiver(calificaciones_guardadas, sender=Calificacion, dispatch_uid="refuerzo_evaluaciones")
def registrar_evaluaciones(sender, actividad, estudiantes, **kwargs):
    services.sincronizar_evaluaciones(actividad, estudiantes)
