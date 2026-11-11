"""
Suscripción a los eventos de los demás módulos (ver signals.py de cada app).

Modelo de negocio (quién recibe qué):
    Representante  actividad publicada / modificada / cancelada  -> ACTIVIDADES
                   nota registrada o corregida (con observación) -> CALIFICACIONES
                   plan de refuerzo aprobado / cancelado / evaluado -> REFUERZO
                   recordatorio de entrega (comando diario)      -> RECORDATORIOS
    Docente        el representante completó el plan (toca evaluar) -> REFUERZO

Los módulos de origen no dependen de este: solo emiten señales.
"""

import logging
from collections import defaultdict

from django.db import transaction
from django.dispatch import receiver

from apps.academic.models import Estudiante
from apps.activities.models import Actividad
from apps.activities.signals import actividad_cancelada, actividad_modificada, actividad_publicada
from apps.grades import scale
from apps.grades.models import Calificacion
from apps.grades.signals import calificaciones_guardadas
from apps.reinforcement.models import PlanRefuerzo
from apps.reinforcement.signals import plan_aprobado, plan_cancelado, plan_completado, plan_evaluado

from .models import Categoria
from .servicio import Correo, notificar

logger = logging.getLogger(__name__)

RUTA_ACTIVIDADES = "/representante/actividades"
CAMPOS_VISIBLES = {
    "descripcion": "Descripción",
    "fecha_entrega": "Fecha de entrega",
    "hora_entrega": "Hora de entrega",
    "tema": "Tema",
    "materiales": "Materiales",
    "modalidad_entrega": "Modalidad de entrega",
}


def _seguro(funcion):
    """Un fallo al notificar nunca debe romper la operación del docente."""

    def envoltura(*args, **kwargs):
        try:
            funcion(*args, **kwargs)
        except Exception:  # pragma: no cover - se registra para revisarlo
            logger.exception("Error al generar notificaciones (%s)", funcion.__name__)

    envoltura.__name__ = funcion.__name__
    return envoltura


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


def _entrega(actividad):
    texto = _fecha(actividad.fecha_entrega)
    if actividad.hora_entrega and actividad.hora_entrega.strftime("%H:%M") != "00:00":
        texto += f" hasta las {actividad.hora_entrega.strftime('%H:%M')}"
    return texto


def _resumen(texto, maximo=160):
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def _estudiantes_por_representante(actividad):
    """{representante: [estudiantes]} de los estudiantes activos del paralelo."""
    grupos = defaultdict(list)
    for e in Estudiante.objects.filter(
        paralelo_id=actividad.asignacion.paralelo_id, is_active=True
    ).select_related("representante"):
        grupos[e.representante].append(e)
    return grupos


def _nombres(estudiantes):
    nombres = [e.first_name.split()[0] for e in estudiantes]
    return nombres[0] if len(nombres) == 1 else ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _detalles_actividad(actividad):
    detalles = [
        ("Asignatura", actividad.asignacion.asignatura.nombre),
        ("Paralelo", actividad.asignacion.paralelo.nombre_completo),
        ("Entrega", _entrega(actividad)),
    ]
    if actividad.tema:
        detalles.append(("Tema", actividad.tema))
    if actividad.materiales:
        detalles.append(("Materiales", ", ".join(actividad.materiales)))
    detalles.append(("Modalidad", actividad.get_modalidad_entrega_display()))
    return detalles


def _actividad(actividad):
    return Actividad.objects.select_related(
        "asignacion__asignatura", "asignacion__paralelo__grado", "asignacion__docente"
    ).get(pk=actividad.pk)


# ---------------------------------------------------------------------------
# Actividades
# ---------------------------------------------------------------------------
@receiver(actividad_publicada, dispatch_uid="notif_actividad_publicada")
@_seguro
def actividad_nueva(sender, actividad, **kwargs):
    a = _actividad(actividad)
    asignatura = a.asignacion.asignatura.nombre
    for representante, estudiantes in _estudiantes_por_representante(a).items():
        quien = _nombres(estudiantes)
        notificar(
            [representante], Categoria.ACTIVIDADES, "actividad_publicada",
            titulo=f"Nueva actividad de {asignatura}",
            mensaje=f"Para {quien}: {_resumen(a.descripcion)} Entrega: {_entrega(a)}.",
            enlace=RUTA_ACTIVIDADES,
            correo=Correo(
                asunto=f"Nueva actividad de {asignatura}",
                parrafos=[f"{a.asignacion.docente.full_name} publicó una actividad para {quien}:", a.descripcion],
                detalles=_detalles_actividad(a),
                boton=("Ver la actividad", RUTA_ACTIVIDADES),
            ),
        )


@receiver(actividad_modificada, dispatch_uid="notif_actividad_modificada")
@_seguro
def actividad_cambiada(sender, actividad, campos=(), **kwargs):
    cambiados = [CAMPOS_VISIBLES[c] for c in campos if c in CAMPOS_VISIBLES]
    if not cambiados:
        return
    a = _actividad(actividad)
    asignatura = a.asignacion.asignatura.nombre
    lista = ", ".join(cambiados).lower()
    for representante, estudiantes in _estudiantes_por_representante(a).items():
        notificar(
            [representante], Categoria.ACTIVIDADES, "actividad_modificada",
            titulo=f"Cambió una actividad de {asignatura}",
            mensaje=f"Se actualizó: {lista}. Entrega: {_entrega(a)}.",
            enlace=RUTA_ACTIVIDADES,
            correo=Correo(
                asunto=f"Cambió una actividad de {asignatura}",
                parrafos=[f"El docente actualizó la actividad de {_nombres(estudiantes)} ({lista}). Así quedó:", a.descripcion],
                detalles=_detalles_actividad(a),
                boton=("Ver la actividad", RUTA_ACTIVIDADES),
            ),
        )


@receiver(actividad_cancelada, dispatch_uid="notif_actividad_cancelada")
@_seguro
def actividad_anulada(sender, actividad, **kwargs):
    a = _actividad(actividad)
    asignatura = a.asignacion.asignatura.nombre
    for representante, estudiantes in _estudiantes_por_representante(a).items():
        notificar(
            [representante], Categoria.ACTIVIDADES, "actividad_cancelada",
            titulo=f"Se canceló una actividad de {asignatura}",
            mensaje=f"Ya no hay que entregar: {_resumen(a.descripcion)}",
            enlace=RUTA_ACTIVIDADES,
            correo=Correo(
                asunto=f"Se canceló una actividad de {asignatura}",
                parrafos=[f"El docente canceló esta actividad de {_nombres(estudiantes)}; ya no hay que entregarla:", a.descripcion],
                detalles=[("Asignatura", asignatura), ("Entrega prevista", _entrega(a))],
                boton=("Ver actividades", RUTA_ACTIVIDADES),
            ),
        )


# ---------------------------------------------------------------------------
# Calificaciones (la señal llega dentro de la transacción: se espera al commit)
# ---------------------------------------------------------------------------
@receiver(calificaciones_guardadas, dispatch_uid="notif_calificaciones")
def notas_guardadas(sender, actividad, estudiantes, **kwargs):
    actividad_id, ids = actividad.pk, list(estudiantes)
    transaction.on_commit(lambda: _avisar_notas(actividad_id, ids))


@_seguro
def _avisar_notas(actividad_id, estudiantes):
    a = Actividad.objects.select_related("asignacion__asignatura", "asignacion__docente").get(pk=actividad_id)
    asignatura = a.asignacion.asignatura.nombre
    notas = Calificacion.objects.filter(actividad_id=actividad_id, estudiante_id__in=estudiantes).select_related(
        "estudiante__representante", "tema__padre"
    )
    for c in notas:
        e = c.estudiante
        if not e.is_active:
            continue
        valor = f"{c.valor:.2f}".replace(".", ",")
        nivel = scale.nombre_nivel(scale.nivel_cualitativo(c.valor)) or ""
        detalles = [("Asignatura", asignatura), ("Tema", str(c.tema)), ("Nota", f"{valor} / 10"), ("Nivel de logro", nivel)]
        if c.observacion:
            detalles.append(("Observación del docente", c.observacion))
        notificar(
            [e.representante], Categoria.CALIFICACIONES, "calificacion",
            titulo=f"{e.first_name.split()[0]} tiene nota en {asignatura}: {valor}",
            mensaje=_resumen(a.descripcion) + (f" Observación: {_resumen(c.observacion, 200)}" if c.observacion else ""),
            enlace=RUTA_ACTIVIDADES,
            correo=Correo(
                asunto=f"Nueva calificación de {e.first_name.split()[0]} en {asignatura}",
                parrafos=[f"{a.asignacion.docente.full_name} registró la nota de {e.full_name} en esta actividad:", a.descripcion],
                detalles=detalles,
                boton=("Ver en EduGest", RUTA_ACTIVIDADES),
            ),
        )


# ---------------------------------------------------------------------------
# Planes de refuerzo
# ---------------------------------------------------------------------------
def _plan(plan):
    return PlanRefuerzo.objects.select_related("estudiante__representante", "asignatura", "docente").get(pk=plan.pk)


def _temas(plan):
    return ", ".join(str(t.tema) for t in plan.temas.select_related("tema__padre"))


@receiver(plan_aprobado, dispatch_uid="notif_plan_aprobado")
@_seguro
def plan_listo(sender, plan, **kwargs):
    p = _plan(plan)
    e = p.estudiante
    ruta = f"/representante/planes/{p.pk}"
    notificar(
        [e.representante], Categoria.REFUERZO, "plan_aprobado",
        titulo=f"Plan de refuerzo de {p.asignatura.nombre} para {e.first_name.split()[0]}",
        mensaje=f"El docente preparó actividades de refuerzo en: {_temas(p)}.",
        enlace=ruta,
        correo=Correo(
            asunto=f"Plan de refuerzo de {p.asignatura.nombre} para {e.first_name.split()[0]}",
            parrafos=[
                f"{p.docente.full_name} preparó un plan de refuerzo para {e.full_name} en {p.asignatura.nombre}.",
                "Revísenlo juntos y marquen cada actividad cuando la terminen. Su acompañamiento en casa hace la diferencia.",
            ],
            detalles=[("Temas", _temas(p)), ("Nivel", p.get_nivel_display())],
            boton=("Ver el plan", ruta),
        ),
    )


@receiver(plan_cancelado, dispatch_uid="notif_plan_cancelado")
@_seguro
def plan_anulado(sender, plan, **kwargs):
    p = _plan(plan)
    if not p.aprobado_en:  # la familia nunca lo vio: no hay nada que avisar
        return
    e = p.estudiante
    notificar(
        [e.representante], Categoria.REFUERZO, "plan_cancelado",
        titulo=f"Se canceló el plan de refuerzo de {p.asignatura.nombre}",
        mensaje=f"El plan de {e.first_name.split()[0]} ya no está vigente.",
        enlace="/representante/planes",
        correo=Correo(
            asunto=f"Se canceló el plan de refuerzo de {p.asignatura.nombre}",
            parrafos=[f"El docente canceló el plan de refuerzo de {e.full_name} en {p.asignatura.nombre}; ya no está vigente."],
            boton=("Ver planes", "/representante/planes"),
        ),
    )


@receiver(plan_completado, dispatch_uid="notif_plan_completado")
@_seguro
def plan_terminado(sender, plan, **kwargs):
    p = _plan(plan)
    e = p.estudiante
    ruta = f"/docente/planes/{p.pk}"
    notificar(
        [p.docente], Categoria.REFUERZO, "plan_completado",
        titulo=f"{e.full_name} completó su plan de {p.asignatura.nombre}",
        mensaje="Todas las actividades están cumplidas. Ya puedes registrar la evaluación de refuerzo.",
        enlace=ruta,
        correo=Correo(
            asunto=f"{e.full_name} completó su plan de refuerzo",
            parrafos=[
                f"Todas las actividades del plan de {p.asignatura.nombre} quedaron cumplidas.",
                "El siguiente paso es aplicar y calificar la evaluación de refuerzo de sus temas.",
            ],
            detalles=[("Estudiante", e.full_name), ("Paralelo", e.paralelo.nombre_completo), ("Temas", _temas(p))],
            boton=("Ver el plan", ruta),
        ),
    )


@receiver(plan_evaluado, dispatch_uid="notif_plan_evaluado")
@_seguro
def plan_con_resultados(sender, plan, **kwargs):
    p = _plan(plan)
    e = p.estudiante
    temas = list(p.temas.select_related("tema__padre"))
    superados = [str(t.tema) for t in temas if t.superado]
    pendientes = [str(t.tema) for t in temas if t.superado is False]
    detalles = []
    if superados:
        detalles.append(("Temas superados", ", ".join(superados)))
    if pendientes:
        detalles.append(("Temas por reforzar", ", ".join(pendientes)))
    ruta = f"/representante/planes/{p.pk}"
    notificar(
        [e.representante], Categoria.REFUERZO, "plan_evaluado",
        titulo=f"Resultados del refuerzo de {p.asignatura.nombre}",
        mensaje=f"{len(superados)} de {len(temas)} temas superados.",
        enlace=ruta,
        correo=Correo(
            asunto=f"Resultados del refuerzo de {e.first_name.split()[0]} en {p.asignatura.nombre}",
            parrafos=[
                f"El docente calificó la evaluación de refuerzo de {e.full_name}.",
                "¡Gracias por acompañar el proceso!" if not pendientes else
                "Algunos temas necesitan más práctica; el docente les indicará los siguientes pasos.",
            ],
            detalles=detalles,
            boton=("Ver resultados", ruta),
        ),
    )
