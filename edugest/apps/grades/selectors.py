"""
Visibilidad por rol de calificaciones y dificultades.

- Administrador: todo (solo consulta).
- Docente: las notas de sus propias actividades, y las dificultades de estudiantes de sus
  paralelos únicamente en los temas de las asignaturas que imparte allí.
- Representante: todo lo de sus estudiantes activos, en todas las asignaturas.
"""

from django.db.models import Exists, OuterRef

from apps.academic.models import AsignacionDocente
from apps.security.models import Role

from .models import Calificacion, Dificultad


def calificaciones_visibles(user):
    qs = Calificacion.objects.select_related(
        "actividad__asignacion__asignatura", "estudiante", "tema"
    )
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(actividad__asignacion__docente=user)
    if user.role == Role.REPRESENTANTE:
        return qs.filter(estudiante__representante=user, estudiante__is_active=True)
    return qs.none()


def dificultades_visibles(user):
    qs = Dificultad.objects.select_related(
        "estudiante__paralelo__grado", "tema__asignatura", "tema__padre"
    )
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        imparte = AsignacionDocente.objects.filter(
            docente=user,
            is_active=True,
            asignatura_id=OuterRef("tema__asignatura_id"),
            paralelo_id=OuterRef("estudiante__paralelo_id"),
        )
        return qs.filter(Exists(imparte))
    if user.role == Role.REPRESENTANTE:
        return qs.filter(estudiante__representante=user, estudiante__is_active=True)
    return qs.none()
