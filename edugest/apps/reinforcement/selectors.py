"""
Visibilidad por rol en el módulo de refuerzo.

- Administrador: todo (solo consulta).
- Docente: los planes de las asignaturas que imparte a esos estudiantes, y los recursos del
  banco de las asignaturas y grados donde enseña.
- Representante: los planes de sus estudiantes que ya fueron aprobados o completados (y los
  cancelados que antes se habían aprobado, para que la familia vea que ya no aplican).
"""

from django.db.models import Exists, OuterRef, Prefetch, Q

from apps.academic.models import AsignacionDocente
from apps.security.models import Role

from .models import ActividadRefuerzo, EvidenciaActividad, PlanRefuerzo, RecursoRefuerzo, TemaPlan

PLAN_PREFETCH = Prefetch(
    "temas",
    queryset=TemaPlan.objects.select_related(
        "tema", "dificultad", "evaluacion__actividad"
    ).prefetch_related(
        Prefetch(
            "actividades",
            queryset=ActividadRefuerzo.objects.select_related("cumplida_por").prefetch_related(
                "evidencias__subida_por"
            ),
        )
    ),
)


def planes_base(user):
    qs = PlanRefuerzo.objects.all()
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        imparte = AsignacionDocente.objects.filter(
            docente=user,
            is_active=True,
            asignatura_id=OuterRef("asignatura_id"),
            paralelo_id=OuterRef("estudiante__paralelo_id"),
        )
        return qs.filter(Exists(imparte))
    if user.role == Role.REPRESENTANTE:
        E = PlanRefuerzo.Estado
        return qs.filter(estudiante__representante=user, estudiante__is_active=True).filter(
            Q(estado__in=[E.APROBADA, E.COMPLETADA])
            | Q(estado=E.CANCELADA, aprobado_en__isnull=False)
        )
    return qs.none()


def planes_visibles(user):
    return (
        planes_base(user)
        .select_related("estudiante__paralelo__grado", "asignatura", "docente", "revisado_por")
        .prefetch_related(PLAN_PREFETCH)
    )


def actividades_refuerzo_visibles(user):
    return (
        ActividadRefuerzo.objects.filter(tema_plan__plan__in=planes_base(user))
        .select_related(
            "tema_plan__plan__estudiante__paralelo", "tema_plan__plan__asignatura", "cumplida_por"
        )
        .prefetch_related("evidencias__subida_por")
    )


def evidencias_visibles(user):
    return EvidenciaActividad.objects.filter(
        actividad__tema_plan__plan__in=planes_base(user)
    ).select_related("actividad__tema_plan__plan", "subida_por")


def temas_plan_visibles(user):
    return (
        TemaPlan.objects.filter(plan__in=planes_base(user))
        .select_related("plan__estudiante__paralelo", "plan__asignatura", "tema", "dificultad")
        .prefetch_related(Prefetch(
            "actividades",
            queryset=ActividadRefuerzo.objects.select_related("cumplida_por").prefetch_related(
                "evidencias__subida_por"
            ),
        ))
    )


def recursos_visibles(user):
    qs = RecursoRefuerzo.objects.select_related(
        "tema__grado", "tema__asignatura", "tema__padre", "creado_por"
    )
    if user.role == Role.ADMINISTRADOR:
        return qs
    if user.role == Role.DOCENTE:
        imparte = AsignacionDocente.objects.filter(
            docente=user,
            is_active=True,
            asignatura_id=OuterRef("tema__asignatura_id"),
            paralelo__grado_id=OuterRef("tema__grado_id"),
        )
        return qs.filter(Exists(imparte))
    return qs.none()


def docente_imparte_en_grado(user, asignatura_id, grado_id):
    return AsignacionDocente.objects.filter(
        docente=user, is_active=True, asignatura_id=asignatura_id, paralelo__grado_id=grado_id
    ).exists()


def estudiantes_para_evaluacion(paralelo_id, asignatura_id):
    """
    Estudiantes a los que se dirige una evaluación de refuerzo: activos del paralelo, con
    un plan de la asignatura COMPLETADO (todas sus actividades cumplidas) y con al menos un
    tema todavía sin evaluar.
    """
    from apps.academic.models import Estudiante

    return (
        Estudiante.objects.filter(
            paralelo_id=paralelo_id,
            is_active=True,
            planes_refuerzo__asignatura_id=asignatura_id,
            planes_refuerzo__estado=PlanRefuerzo.Estado.COMPLETADA,
            planes_refuerzo__temas__superado__isnull=True,
        )
        .distinct()
        .order_by("last_name", "first_name")
    )


def tema_en_plan_completado(estudiante_id, asignatura_id, tema):
    """True si el tema (o su tema padre) está en un plan COMPLETADO del estudiante."""
    ids = [tema.id] + ([tema.padre_id] if tema.padre_id else [])
    return TemaPlan.objects.filter(
        plan__estudiante_id=estudiante_id,
        plan__asignatura_id=asignatura_id,
        plan__estado=PlanRefuerzo.Estado.COMPLETADA,
        tema_id__in=ids,
    ).exists()
