"""
Consultas reutilizables del módulo de actividades.

Visibilidad por rol:
- Administrador: todas las actividades.
- Docente: las de las asignaciones que tiene a su cargo.
- Representante: las de los paralelos donde tiene estudiantes activos (incluidas las
  canceladas, para que la familia vea que ya no deben cumplirlas). Una evaluación de
  refuerzo solo la ve si uno de sus estudiantes es destinatario.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from apps.academic.asignaturas import solo_habilitadas
from apps.security.models import Role

from .models import Actividad

_RELACIONES = (
    "asignacion__docente",
    "asignacion__paralelo__grado",
    "asignacion__asignatura",
)


def actividades_visibles(user):
    qs = Actividad.objects.select_related(*_RELACIONES).prefetch_related("adjuntos", "destinatarios")
    qs = solo_habilitadas(qs, "asignacion__asignatura_id")
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(asignacion__docente=user)
    if user.role == Role.REPRESENTANTE:
        # Las evaluaciones de refuerzo solo las ven las familias de sus destinatarios.
        return qs.filter(
            Q(es_evaluacion_refuerzo=False)
            | Q(destinatarios__representante=user, destinatarios__is_active=True),
            asignacion__paralelo__estudiantes__representante=user,
            asignacion__paralelo__estudiantes__is_active=True,
        ).distinct()
    return qs.none()


def actividades_para_recordatorio(hoy=None, dias_antes=1):
    """Actividades publicadas cuya entrega vence dentro de `dias_antes` días (comando de recordatorios)."""
    hoy = hoy or timezone.localdate()
    qs = Actividad.objects.select_related(*_RELACIONES).filter(
        estado=Actividad.Estado.PUBLICADA,
        fecha_entrega=hoy + timedelta(days=dias_antes),
    )
    return solo_habilitadas(qs, "asignacion__asignatura_id")
