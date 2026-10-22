"""
Reglas de visibilidad por rol. Son la fuente única de verdad sobre "quién ve qué":
los módulos siguientes (actividades, calificaciones, refuerzo) deben apoyarse en estas
funciones en lugar de repetir la lógica.

- Administrador: ve todo.
- Docente: ve solo los paralelos donde tiene una asignación activa, y los estudiantes de
  esos paralelos.
- Representante: ve solo a sus estudiantes activos, su paralelo y las asignaciones
  (docente + asignatura) de ese paralelo.
"""

from apps.security.models import Role

from .models import AsignacionDocente, Estudiante, Paralelo


def paralelos_visibles(user):
    qs = Paralelo.objects.select_related("grado")
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(asignaciones__docente=user, asignaciones__is_active=True).distinct()
    if user.role == Role.REPRESENTANTE:
        return qs.filter(
            estudiantes__representante=user, estudiantes__is_active=True
        ).distinct()
    return qs.none()


def estudiantes_visibles(user):
    qs = Estudiante.objects.select_related("paralelo__grado", "representante")
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(
            paralelo__asignaciones__docente=user,
            paralelo__asignaciones__is_active=True,
        ).distinct()
    if user.role == Role.REPRESENTANTE:
        return qs.filter(representante=user)
    return qs.none()


def asignaciones_visibles(user):
    qs = AsignacionDocente.objects.select_related(
        "docente", "paralelo__grado", "asignatura"
    )
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(docente=user)
    if user.role == Role.REPRESENTANTE:
        return qs.filter(
            paralelo__estudiantes__representante=user,
            paralelo__estudiantes__is_active=True,
            is_active=True,
        ).distinct()
    return qs.none()


# --- Comprobaciones puntuales para usar en permisos de otros módulos ---------------


def puede_ver_estudiante(user, estudiante_id):
    return estudiantes_visibles(user).filter(pk=estudiante_id).exists()


def docente_imparte(user, paralelo_id, asignatura_id):
    """True si el docente tiene una asignación activa en ese paralelo y asignatura."""
    return AsignacionDocente.objects.filter(
        docente=user,
        paralelo_id=paralelo_id,
        asignatura_id=asignatura_id,
        is_active=True,
    ).exists()
