"""
Lógica de negocio del refuerzo académico. Las vistas validan la entrada y delegan aquí.
"""

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.academic import selectors as academic_selectors
from apps.grades import scale
from apps.grades.models import Calificacion, Dificultad

from . import rules
from .models import ActividadRefuerzo, PlanRefuerzo, RecursoRefuerzo, TemaPlan
from .signals import (
    actividad_refuerzo_cumplida,
    plan_aprobado,
    plan_cancelado,
    plan_completado,
    plan_evaluado,
)

Estado = PlanRefuerzo.Estado


def _emitir(senal, **kwargs):
    transaction.on_commit(lambda: senal.send(sender=PlanRefuerzo, **kwargs))


def verificar_editable(plan):
    if plan.estado != Estado.PROPUESTA:
        raise ValidationError(
            {"detail": "El plan ya no está en propuesta; solo se puede editar mientras es una propuesta."}
        )


# ---------------------------------------------------------------------------
# Generación (motor de reglas)
# ---------------------------------------------------------------------------
def _seleccionar_recursos(tema, nivel, ya_asignados):
    """
    Elige actividades del banco para un tema según `rules`. Busca primero en el tema exacto
    y, si no hay nada y es un subtema, en su tema padre. Dentro de cada nivel prefiere los
    recursos que el estudiante aún no ha recibido.
    """
    regla = rules.ACTIVIDADES_POR_DIFICULTAD[nivel]
    candidatos = [tema] + ([tema.padre] if tema.padre_id else [])

    for candidato in candidatos:
        elegidos = []
        for nivel_actividad, cantidad in regla.items():
            del_nivel = RecursoRefuerzo.objects.filter(
                tema=candidato, nivel=nivel_actividad, is_active=True
            ).order_by("id")
            ordenados = sorted(del_nivel, key=lambda r: (r.id in ya_asignados, r.id))
            elegidos.extend(ordenados[:cantidad])
        if elegidos:
            return elegidos
    return []


def _validar_temas_manuales(estudiante, asignatura, temas_manuales, dificultades):
    """Comprueba los temas que el docente pidió reforzar a mano y los devuelve con su motivo."""
    grado_id = estudiante.paralelo.grado_id
    detectadas = {d.tema_id for d in dificultades}
    vistos = set()
    validados = []
    for item in temas_manuales:
        tema = item["tema"]
        motivo = " ".join((item.get("motivo") or "").split())
        if tema.id in vistos:
            raise ValidationError({"temas_manuales": f"El tema «{tema.nombre}» está repetido."})
        vistos.add(tema.id)
        if tema.asignatura_id != asignatura.id or tema.grado_id != grado_id:
            raise ValidationError(
                {"temas_manuales": f"El tema «{tema.nombre}» no corresponde a la asignatura y el grado del estudiante."}
            )
        if tema.id in detectadas:
            raise ValidationError(
                {"temas_manuales": f"«{tema.nombre}» ya tiene una dificultad detectada: se incluye solo en el plan."}
            )
        validados.append((tema, motivo))
    return validados


@transaction.atomic
def generar_plan(docente, estudiante, asignatura, temas_manuales=None):
    """
    Genera una propuesta de plan para un estudiante en una asignatura que el docente imparte.

    El plan se arma con las dificultades detectadas (las de menor promedio primero) y, si el
    docente lo pide, con temas de refuerzo manual (temas sin dificultad detectada). En total
    nunca pasa de `rules.MAX_TEMAS_POR_PLAN` temas; los manuales tienen prioridad.
    """
    temas_manuales = temas_manuales or []
    if not estudiante.is_active:
        raise ValidationError({"estudiante": "El estudiante está inactivo."})
    if not academic_selectors.docente_imparte(docente, estudiante.paralelo_id, asignatura.id):
        raise ValidationError({"asignatura": "No impartes esa asignatura a este estudiante."})

    vigente = PlanRefuerzo.objects.filter(
        estudiante=estudiante, asignatura=asignatura, estado__in=PlanRefuerzo.VIGENTES
    ).first()
    if vigente:
        raise ValidationError(
            {
                "detail": f"Ya existe un plan {vigente.get_estado_display().lower()} "
                f"(#{vigente.id}) para este estudiante en {asignatura.nombre}."
            }
        )

    todas = list(
        Dificultad.objects.select_related("tema__padre", "tema__asignatura")
        .filter(estudiante=estudiante, estado=Dificultad.Estado.DETECTADA, tema__asignatura=asignatura)
        .order_by("promedio", "id")
    )
    manuales = _validar_temas_manuales(estudiante, asignatura, temas_manuales, todas)

    if len(manuales) > rules.MAX_TEMAS_POR_PLAN:
        raise ValidationError(
            {"temas_manuales": f"Un plan cubre como máximo {rules.MAX_TEMAS_POR_PLAN} temas."}
        )
    dificultades = todas[: rules.MAX_TEMAS_POR_PLAN - len(manuales)]
    if not dificultades and not manuales:
        raise ValidationError(
            {
                "detail": "El estudiante no tiene dificultades detectadas en esta asignatura. "
                "Puedes pedir el refuerzo de un tema concreto."
            }
        )

    try:
        with transaction.atomic():
            plan = PlanRefuerzo.objects.create(
                estudiante=estudiante,
                asignatura=asignatura,
                docente=docente,
                nivel=rules.nivel_plan([d.nivel for d in dificultades]),
            )
    except IntegrityError:
        raise ValidationError({"detail": "Ya existe un plan vigente para este estudiante y asignatura."})

    ya_asignados = set(
        ActividadRefuerzo.objects.filter(
            tema_plan__plan__estudiante=estudiante, recurso__isnull=False
        ).values_list("recurso_id", flat=True)
    )

    def crear_actividades(tema_plan, recursos):
        for posicion, recurso in enumerate(recursos, start=1):
            ActividadRefuerzo.objects.create(
                tema_plan=tema_plan,
                recurso=recurso,
                origen=ActividadRefuerzo.Origen.BANCO,
                titulo=recurso.titulo,
                instrucciones=recurso.instrucciones,
                duracion_minutos=recurso.duracion_minutos,
                nivel=recurso.nivel,
                estrategia=recurso.estrategia,
                orden=posicion,
            )

    orden = 0
    for tema, motivo in manuales:
        orden += 1
        valores = Calificacion.objects.filter(estudiante=estudiante, tema=tema).values_list(
            "valor", flat=True
        )
        recursos = _seleccionar_recursos(tema, rules.NIVEL_MANUAL, ya_asignados)
        tema_plan = TemaPlan.objects.create(
            plan=plan,
            tema=tema,
            dificultad=None,
            origen=TemaPlan.Origen.MANUAL,
            motivo=motivo,
            orden=orden,
            objetivo=rules.objetivo_manual(tema.nombre, asignatura.nombre, motivo),
            promedio_inicial=scale.promedio(valores),
            nivel_dificultad=rules.NIVEL_MANUAL,
            sin_recursos=not recursos,
        )
        crear_actividades(tema_plan, recursos)

    for dificultad in dificultades:
        orden += 1
        recursos = _seleccionar_recursos(dificultad.tema, dificultad.nivel, ya_asignados)
        tema_plan = TemaPlan.objects.create(
            plan=plan,
            tema=dificultad.tema,
            dificultad=dificultad,
            orden=orden,
            objetivo=rules.objetivo_para(dificultad.tema.nombre, asignatura.nombre, dificultad.promedio),
            promedio_inicial=dificultad.promedio,
            nivel_dificultad=dificultad.nivel,
            sin_recursos=not recursos,
        )
        crear_actividades(tema_plan, recursos)
    return plan


# ---------------------------------------------------------------------------
# Edición de la propuesta
# ---------------------------------------------------------------------------
@transaction.atomic
def agregar_actividad(
    tema_plan, *, recurso=None, titulo=None, instrucciones=None, duracion_minutos=None, estrategia=""
):
    plan = tema_plan.plan
    verificar_editable(plan)

    if tema_plan.actividades.count() >= rules.MAX_ACTIVIDADES_POR_TEMA:
        raise ValidationError(
            {"detail": f"Un tema no puede tener más de {rules.MAX_ACTIVIDADES_POR_TEMA} actividades."}
        )

    siguiente = (tema_plan.actividades.aggregate(m=Max("orden"))["m"] or 0) + 1

    if recurso is not None:
        if (
            recurso.tema.asignatura_id != plan.asignatura_id
            or recurso.tema.grado_id != plan.estudiante.paralelo.grado_id
        ):
            raise ValidationError(
                {"recurso": "El recurso no corresponde a la asignatura y el grado del plan."}
            )
        if tema_plan.actividades.filter(recurso=recurso).exists():
            raise ValidationError({"recurso": "Ese recurso ya está en este tema del plan."})
        return ActividadRefuerzo.objects.create(
            tema_plan=tema_plan,
            recurso=recurso,
            origen=ActividadRefuerzo.Origen.BANCO,
            titulo=recurso.titulo,
            instrucciones=recurso.instrucciones,
            duracion_minutos=recurso.duracion_minutos,
            nivel=recurso.nivel,
            estrategia=recurso.estrategia,
            orden=siguiente,
        )

    return ActividadRefuerzo.objects.create(
        tema_plan=tema_plan,
        origen=ActividadRefuerzo.Origen.MANUAL,
        titulo=titulo,
        instrucciones=instrucciones,
        duracion_minutos=duracion_minutos,
        estrategia=estrategia or "",
        orden=siguiente,
    )


# ---------------------------------------------------------------------------
# Aprobación y cancelación
# ---------------------------------------------------------------------------
@transaction.atomic
def aprobar_plan(plan, usuario):
    plan = PlanRefuerzo.objects.select_for_update().get(pk=plan.pk)
    if plan.estado != Estado.PROPUESTA:
        raise ValidationError({"detail": "Solo se puede aprobar un plan que está en propuesta."})
    if not ActividadRefuerzo.objects.filter(tema_plan__plan=plan).exists():
        raise ValidationError(
            {"detail": "El plan no tiene actividades. Agrega al menos una antes de aprobarlo."}
        )
    plan.estado = Estado.APROBADA
    plan.aprobado_por = usuario
    plan.aprobado_en = timezone.now()
    plan.save()
    _emitir(plan_aprobado, plan=plan)
    return plan


@transaction.atomic
def cancelar_plan(plan, usuario):
    plan = PlanRefuerzo.objects.select_for_update().get(pk=plan.pk)
    if plan.estado not in PlanRefuerzo.VIGENTES:
        raise ValidationError({"detail": "Solo se puede cancelar un plan en propuesta o aprobado."})
    plan.estado = Estado.CANCELADA
    plan.cancelado_en = timezone.now()
    plan.save()
    _emitir(plan_cancelado, plan=plan)
    return plan


# ---------------------------------------------------------------------------
# Seguimiento
# ---------------------------------------------------------------------------
@transaction.atomic
def cumplir_actividad(actividad, usuario):
    """Marca una actividad como cumplida (docente o representante). Devuelve (actividad, plan)."""
    plan = PlanRefuerzo.objects.select_for_update().get(pk=actividad.tema_plan.plan_id)
    if plan.estado != Estado.APROBADA:
        raise ValidationError({"detail": "Solo se pueden marcar actividades de un plan aprobado vigente."})
    if actividad.estado == ActividadRefuerzo.Estado.CUMPLIDA:
        raise ValidationError({"detail": "La actividad ya está marcada como cumplida."})

    actividad.estado = ActividadRefuerzo.Estado.CUMPLIDA
    actividad.cumplida_en = timezone.now()
    actividad.cumplida_por = usuario
    actividad.save()
    _emitir(actividad_refuerzo_cumplida, actividad=actividad, plan=plan, cumplida_por=usuario)

    pendientes = ActividadRefuerzo.objects.filter(
        tema_plan__plan=plan, estado=ActividadRefuerzo.Estado.PENDIENTE
    ).exists()
    if not pendientes:
        plan.estado = Estado.COMPLETADA
        plan.completado_en = timezone.now()
        plan.save()
        _emitir(plan_completado, plan=plan)
    return actividad, plan


@transaction.atomic
def reabrir_actividad(actividad, usuario):
    """Corrige un cumplimiento marcado por error (solo el docente). Devuelve (actividad, plan)."""
    plan = PlanRefuerzo.objects.select_for_update().get(pk=actividad.tema_plan.plan_id)
    if plan.estado not in (Estado.APROBADA, Estado.COMPLETADA):
        raise ValidationError({"detail": "El plan no admite cambios de seguimiento."})
    if actividad.estado != ActividadRefuerzo.Estado.CUMPLIDA:
        raise ValidationError({"detail": "La actividad no está marcada como cumplida."})

    actividad.estado = ActividadRefuerzo.Estado.PENDIENTE
    actividad.cumplida_en = None
    actividad.cumplida_por = None
    actividad.save()
    if plan.estado == Estado.COMPLETADA:
        plan.estado = Estado.APROBADA
        plan.completado_en = None
        plan.save()
        # El plan vuelve a estar en curso: la evaluación anterior deja de valer.
        plan.temas.update(evaluacion=None, promedio_final=None, superado=None, evaluado_en=None)
    return actividad, plan


# ---------------------------------------------------------------------------
# Evaluación de refuerzo
# ---------------------------------------------------------------------------
def _nota_de_evaluacion(tema_plan):
    """
    Última nota del estudiante en una actividad marcada como evaluación de refuerzo, en el
    tema del plan (o en uno de sus subtemas), registrada después de completar el plan.
    """
    plan = tema_plan.plan
    return (
        Calificacion.objects.filter(
            estudiante_id=plan.estudiante_id,
            actividad__es_evaluacion_refuerzo=True,
            actividad__estado="PUBLICADA",
            created_at__gte=plan.completado_en,
        )
        .filter(Q(tema_id=tema_plan.tema_id) | Q(tema__padre_id=tema_plan.tema_id))
        .order_by("-created_at", "-id")
        .first()
    )


def evaluar_tema(tema_plan, ahora=None):
    """
    Registra (o actualiza) el resultado de la evaluación de un tema del plan completado.

    - Tema con dificultad detectada: se supera si el promedio del tema, con la nota de la
      evaluación incluida, llega a 7,00 (la misma regla que cierra la dificultad).
    - Tema de refuerzo manual (ya promediaba 7 o más): se supera si la nota de la
      evaluación es de 7,00 o más.
    Devuelve True si el tema quedó evaluado.
    """
    nota = _nota_de_evaluacion(tema_plan)
    if nota is None:
        cambios = dict(evaluacion=None, promedio_final=None, superado=None, evaluado_en=None)
    else:
        valores = Calificacion.objects.filter(
            estudiante_id=tema_plan.plan.estudiante_id, tema_id=nota.tema_id
        ).values_list("valor", flat=True)
        promedio = scale.promedio(valores)
        if tema_plan.origen == TemaPlan.Origen.DIFICULTAD:
            superado = promedio >= scale.UMBRAL_ALCANZA
        else:
            superado = nota.valor >= scale.UMBRAL_ALCANZA
        mismo = tema_plan.evaluacion_id == nota.id and tema_plan.evaluado_en
        cambios = dict(
            evaluacion=nota,
            promedio_final=promedio,
            superado=superado,
            evaluado_en=tema_plan.evaluado_en if mismo else (ahora or timezone.now()),
        )
    for campo, valor in cambios.items():
        setattr(tema_plan, campo, valor)
    tema_plan.save(update_fields=list(cambios))
    return nota is not None


def sincronizar_evaluaciones(actividad, estudiante_ids):
    """
    Se llama al guardar notas de una actividad marcada como evaluación de refuerzo:
    actualiza los temas de los planes COMPLETADOS de esos estudiantes en la asignatura.
    Se recalcula todo el tema, así que corregir la nota o cambiar el tema también se refleja.
    """
    if not actividad.es_evaluacion_refuerzo or not estudiante_ids:
        return []
    planes = (
        PlanRefuerzo.objects.select_for_update()
        .filter(
            estudiante_id__in=estudiante_ids,
            asignatura_id=actividad.asignacion.asignatura_id,
            estado=Estado.COMPLETADA,
        )
        .prefetch_related("temas")
    )
    ahora = timezone.now()
    evaluados = []
    for plan in planes:
        antes = all(t.superado is not None for t in plan.temas.all())
        for tema_plan in plan.temas.all():
            tema_plan.plan = plan
            evaluar_tema(tema_plan, ahora)
        despues = all(t.superado is not None for t in plan.temas.all())
        if despues and not antes:
            _emitir(plan_evaluado, plan=plan)
        evaluados.append(plan)
    return evaluados
