"""
Lógica de negocio de calificaciones. Las vistas solo validan la entrada y delegan aquí.
"""

from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.activities.models import Actividad
from apps.security.models import Role

from . import scale
from .models import Calificacion, CalificacionHistorial, Dificultad
from .signals import calificaciones_guardadas, dificultad_detectada, dificultad_superada


def minimo_calificaciones():
    """Notas mínimas en un tema para poder hablar de dificultad (ajustable en settings)."""
    return int(getattr(settings, "GRADES_MIN_CALIFICACIONES", 1))


# ---------------------------------------------------------------------------
# Reglas para poder calificar
# ---------------------------------------------------------------------------
def verificar_calificable(actividad, hoy=None):
    hoy = hoy or timezone.localdate()
    if actividad.estado == Actividad.Estado.CANCELADA:
        raise ValidationError({"detail": "No se puede calificar una actividad cancelada."})
    if not actividad.asignacion.is_active:
        raise ValidationError({"detail": "La asignación docente de esta actividad está inactiva."})
    if actividad.fecha_entrega > hoy:
        raise ValidationError(
            {
                "detail": "Solo se puede calificar desde el día de entrega "
                f"({actividad.fecha_entrega:%d/%m/%Y})."
            }
        )


# ---------------------------------------------------------------------------
# Dificultades
# ---------------------------------------------------------------------------
def recalcular_dificultad(estudiante_id, tema_id):
    """
    Recalcula, con las notas del estudiante en ese tema, si hay dificultad:
    - promedio < 7,00 -> dificultad DETECTADA (moderada o alta); si estaba superada, se reabre.
    - promedio >= 7,00 -> si estaba DETECTADA pasa a SUPERADA.
    Las notas de un subtema no cuentan para el tema padre: cada nodo se evalúa por separado.
    """
    valores = list(
        Calificacion.objects.filter(estudiante_id=estudiante_id, tema_id=tema_id).values_list(
            "valor", flat=True
        )
    )
    existente = (
        Dificultad.objects.select_for_update()
        .filter(estudiante_id=estudiante_id, tema_id=tema_id)
        .first()
    )

    if not valores:
        # La última nota del tema se movió a otro tema: ya no hay evidencia que sostenga la dificultad.
        if existente and existente.estado == Dificultad.Estado.DETECTADA:
            existente.estado = Dificultad.Estado.SUPERADA
            existente.superada_en = timezone.now()
            existente.save()
            _emitir(dificultad_superada, existente)
        return existente

    if len(valores) < minimo_calificaciones():
        return existente

    prom = scale.promedio(valores)
    nivel = scale.nivel_dificultad(prom)

    if nivel is None:
        if existente is None:
            return None
        reciente_superada = existente.estado == Dificultad.Estado.DETECTADA
        existente.promedio = prom
        existente.num_calificaciones = len(valores)
        if reciente_superada:
            existente.estado = Dificultad.Estado.SUPERADA
            existente.superada_en = timezone.now()
        existente.save()
        if reciente_superada:
            _emitir(dificultad_superada, existente)
        return existente

    if existente is None:
        dificultad = Dificultad.objects.create(
            estudiante_id=estudiante_id,
            tema_id=tema_id,
            promedio=prom,
            num_calificaciones=len(valores),
            nivel=nivel,
        )
        _emitir(dificultad_detectada, dificultad)
        return dificultad

    reabierta = existente.estado == Dificultad.Estado.SUPERADA
    existente.promedio = prom
    existente.num_calificaciones = len(valores)
    existente.nivel = nivel
    existente.estado = Dificultad.Estado.DETECTADA
    existente.superada_en = None
    existente.save()
    if reabierta:
        _emitir(dificultad_detectada, existente)
    return existente


def _emitir(senal, dificultad):
    transaction.on_commit(lambda: senal.send(sender=Dificultad, dificultad=dificultad))


# ---------------------------------------------------------------------------
# Guardado masivo
# ---------------------------------------------------------------------------
@transaction.atomic
def guardar_calificaciones(actividad, tema, items, usuario):
    """
    Crea o actualiza las notas de varios estudiantes en una actividad.

    items: lista de (estudiante_id, valor: Decimal). Los estudiantes no incluidos no
    cambian. Cada corrección de una nota existente deja un registro de historial.
    Devuelve un diccionario con los conteos, las notas tocadas y las dificultades vigentes
    de los estudiantes/temas afectados.
    """
    ids = [estudiante_id for estudiante_id, _ in items]
    existentes = {
        c.estudiante_id: c
        for c in Calificacion.objects.select_for_update().filter(
            actividad=actividad, estudiante_id__in=ids
        )
    }

    creadas = actualizadas = sin_cambios = 0
    afectados = set()  # (estudiante_id, tema_id) a recalcular
    tocadas = []

    for estudiante_id, valor in items:
        calificacion = existentes.get(estudiante_id)

        if calificacion is None:
            calificacion = Calificacion.objects.create(
                actividad=actividad,
                estudiante_id=estudiante_id,
                tema=tema,
                valor=valor,
                registrada_por=usuario,
            )
            creadas += 1
            afectados.add((estudiante_id, tema.id))
        elif calificacion.valor == valor and calificacion.tema_id == tema.id:
            sin_cambios += 1
        else:
            CalificacionHistorial.objects.create(
                calificacion=calificacion,
                valor_anterior=calificacion.valor,
                valor_nuevo=valor,
                tema_anterior_id=calificacion.tema_id,
                tema_nuevo=tema,
                modificado_por=usuario,
            )
            afectados.add((estudiante_id, calificacion.tema_id))
            afectados.add((estudiante_id, tema.id))
            calificacion.valor = valor
            calificacion.tema = tema
            calificacion.save()
            actualizadas += 1
        tocadas.append(calificacion.pk)

    for estudiante_id, tema_id in sorted(afectados):
        recalcular_dificultad(estudiante_id, tema_id)

    if afectados:
        calificaciones_guardadas.send(
            sender=Calificacion,
            actividad=actividad,
            estudiantes=sorted({e for e, _ in afectados}),
        )

    vigentes = []
    if afectados:
        vigentes = list(
            Dificultad.objects.filter(
                estado=Dificultad.Estado.DETECTADA,
                estudiante_id__in={e for e, _ in afectados},
                tema_id__in={t for _, t in afectados},
            )
            .select_related("estudiante__paralelo__grado", "tema__asignatura")
        )
        vigentes = [d for d in vigentes if (d.estudiante_id, d.tema_id) in afectados]

    return {
        "creadas": creadas,
        "actualizadas": actualizadas,
        "sin_cambios": sin_cambios,
        "calificaciones_ids": tocadas,
        "dificultades": vigentes,
    }


# ---------------------------------------------------------------------------
# Desempeño de un estudiante
# ---------------------------------------------------------------------------
def _datos_promedio(valores):
    prom = scale.promedio(valores)
    nivel = scale.nivel_cualitativo(prom)
    return {
        "promedio": str(prom) if prom is not None else None,
        "nivel": nivel,
        "nivel_nombre": scale.nombre_nivel(nivel),
        "calificaciones": len(valores),
    }


def desempeno_estudiante(estudiante, user):
    """
    Resumen del desempeño por asignatura y tema (con subtemas anidados).

    - El docente solo ve las notas de las asignaturas que tiene a su cargo.
    - El representante y el administrador ven todas las asignaturas.
    - El promedio de un tema padre incluye las notas de sus subtemas (solo para mostrar);
      la detección de dificultades evalúa cada tema o subtema por separado.
    """
    califs = Calificacion.objects.filter(estudiante=estudiante).select_related(
        "tema__asignatura", "tema__padre"
    )
    if user.role == Role.DOCENTE:
        califs = califs.filter(actividad__asignacion__docente=user)

    valores_por_tema = defaultdict(list)
    valores_por_asignatura = defaultdict(list)
    temas = {}
    asignaturas = {}
    for c in califs:
        valores_por_tema[c.tema_id].append(c.valor)
        valores_por_asignatura[c.tema.asignatura_id].append(c.valor)
        temas[c.tema_id] = c.tema
        asignaturas[c.tema.asignatura_id] = c.tema.asignatura

    # Un subtema sin notas propias en el padre igualmente necesita mostrar a su padre.
    for tema in list(temas.values()):
        if tema.padre_id and tema.padre_id not in temas:
            temas[tema.padre_id] = tema.padre

    hijos_de = defaultdict(list)
    for tema in temas.values():
        if tema.padre_id:
            hijos_de[tema.padre_id].append(tema)

    dificultades = {
        d.tema_id: d
        for d in Dificultad.objects.filter(estudiante=estudiante, tema_id__in=list(temas))
    }

    def nodo(tema):
        valores = list(valores_por_tema.get(tema.id, []))
        for hijo in hijos_de.get(tema.id, []):
            valores += valores_por_tema.get(hijo.id, [])
        dificultad = dificultades.get(tema.id)
        return {
            "tema": tema.id,
            "nombre": tema.nombre,
            **_datos_promedio(valores),
            "dificultad": (
                {"nivel": dificultad.nivel, "estado": dificultad.estado} if dificultad else None
            ),
            "subtemas": [
                nodo(hijo) for hijo in sorted(hijos_de.get(tema.id, []), key=lambda t: t.nombre)
            ],
        }

    resultado = []
    for asignatura_id, asignatura in sorted(asignaturas.items(), key=lambda kv: kv[1].nombre):
        raices = sorted(
            (t for t in temas.values() if t.padre_id is None and t.asignatura_id == asignatura_id),
            key=lambda t: t.nombre,
        )
        resultado.append(
            {
                "asignatura": asignatura_id,
                "nombre": asignatura.nombre,
                **_datos_promedio(valores_por_asignatura[asignatura_id]),
                "temas": [nodo(t) for t in raices],
            }
        )

    return {
        "estudiante": {
            "id": estudiante.id,
            "nombre": estudiante.full_name,
            "paralelo": estudiante.paralelo.nombre_completo,
        },
        "asignaturas": resultado,
    }
