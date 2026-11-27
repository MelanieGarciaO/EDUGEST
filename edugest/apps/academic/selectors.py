"""
Reglas de visibilidad por rol. Son la fuente única de verdad sobre "quién ve qué":
los módulos siguientes (actividades, calificaciones, refuerzo) deben apoyarse en estas
funciones en lugar de repetir la lógica.

- Administrador: ve todo.
- Docente: ve solo los paralelos donde tiene una asignación activa, y los estudiantes de
  esos paralelos.
- Representante: ve solo a sus estudiantes activos, su paralelo y las asignaciones
  (docente + asignatura) de ese paralelo.

En todos los casos solo cuentan las asignaturas habilitadas (ver asignaturas.py).
"""

from apps.security.models import Role

from .asignaturas import ids_habilitados, restringe
from .models import AsignacionDocente, Estudiante, Paralelo


def _asignatura_habilitada(prefijo):
    """Filtro por asignatura habilitada sobre la relación `prefijo` (vacío si no se restringe)."""
    return {f"{prefijo}asignatura_id__in": ids_habilitados()} if restringe() else {}


def paralelos_visibles(user):
    qs = Paralelo.objects.select_related("grado")
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        return qs.filter(
            asignaciones__docente=user, asignaciones__is_active=True, **_asignatura_habilitada("asignaciones__")
        ).distinct()
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
            **_asignatura_habilitada("paralelo__asignaciones__"),
        ).distinct()
    if user.role == Role.REPRESENTANTE:
        return qs.filter(representante=user)
    return qs.none()


def asignaciones_visibles(user):
    qs = AsignacionDocente.objects.select_related(
        "docente", "paralelo__grado", "asignatura"
    ).filter(**_asignatura_habilitada(""))
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


def asignaciones_activas_de(docente, **filtros):
    """
    Asignaciones activas del docente en asignaturas habilitadas. Base de las reglas «el docente
    imparte...» de todos los módulos; admite OuterRef en los filtros para usarla con Exists.
    """
    return AsignacionDocente.objects.filter(
        docente=docente, is_active=True, **_asignatura_habilitada(""), **filtros
    )


def docente_imparte(user, paralelo_id, asignatura_id):
    """True si el docente tiene una asignación activa en ese paralelo y asignatura."""
    return asignaciones_activas_de(user, paralelo_id=paralelo_id, asignatura_id=asignatura_id).exists()
