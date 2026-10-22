"""
Consultas reutilizables del módulo de actividades.

Visibilidad por rol:
- Administrador: todas las actividades.
- Docente: las de las asignaciones que tiene a su cargo.
- Representante: las de los paralelos donde tiene estudiantes activos (incluidas las
  canceladas, para que la familia vea que ya no deben cumplirlas).
"""

from datetime import timedelta

from django.utils import timezone

from apps.security.models import Role, User

from .models import Actividad

_RELACIONES = (
    "asignacion__docente",
    "asignacion__paralelo__grado",
    "asignacion__asignatura",
)


def actividades_visibles(user):
    qs = Actividad.objects.select_related(*_RELACIONES)
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(asignacion__docente=user)
    if user.role == Role.REPRESENTANTE:
        return qs.filter(
            asignacion__paralelo__estudiantes__representante=user,
            asignacion__paralelo__estudiantes__is_active=True,
        ).distinct()
    return qs.none()


def representantes_de_actividad(actividad):
    """Representantes activos con algún estudiante activo en el paralelo (sin repetidos)."""
    return User.objects.filter(
        role=Role.REPRESENTANTE,
        is_active=True,
        estudiantes_representados__paralelo_id=actividad.asignacion.paralelo_id,
        estudiantes_representados__is_active=True,
    ).distinct()


def actividades_para_recordatorio(hoy=None, dias_antes=1):
    """Actividades publicadas cuya entrega vence dentro de `dias_antes` días."""
    hoy = hoy or timezone.localdate()
    return Actividad.objects.select_related(*_RELACIONES).filter(
        estado=Actividad.Estado.PUBLICADA,
        fecha_entrega=hoy + timedelta(days=dias_antes),
    )
