"""
Parámetros y reglas del motor de generación de planes de refuerzo. Están aquí, separados
de la lógica, para poder ajustarlos sin tocar el resto del código.

Reglas acordadas para el proyecto (propuesta de EduGest; validar con la guía oficial del
Ministerio de Educación sobre refuerzo académico):

- Un plan cubre como máximo 3 temas prioritarios: los de menor promedio.
- Nivel del plan: ALTO si algún tema del plan tiene dificultad ALTA; REGULAR en otro caso.
- Actividades por tema según la dificultad (banco clasificado por nivel de la actividad):
      dificultad ALTA      -> 2 básicas + 2 intermedias
      dificultad MODERADA  -> 1 básica  + 2 intermedias
"""

from apps.grades import scale

MAX_TEMAS_POR_PLAN = 3
MAX_ACTIVIDADES_POR_TEMA = 10

# Orden de las claves = orden en que se agregan las actividades al plan.
ACTIVIDADES_POR_DIFICULTAD = {
    scale.ALTA: {"BASICO": 2, "INTERMEDIO": 2},
    scale.MODERADA: {"BASICO": 1, "INTERMEDIO": 2},
}

# Refuerzo pedido a mano por el docente en un tema sin dificultad detectada (por ejemplo, el
# estudiante promedia 7 o más pero falla en una destreza): carga ligera.
NIVEL_MANUAL = "MANUAL"
ACTIVIDADES_POR_DIFICULTAD[NIVEL_MANUAL] = {"BASICO": 1, "INTERMEDIO": 2}

PLAN_ALTO = "ALTO"
PLAN_REGULAR = "REGULAR"


def nivel_plan(niveles_dificultad):
    return PLAN_ALTO if scale.ALTA in niveles_dificultad else PLAN_REGULAR


def objetivo_para(tema_nombre, asignatura_nombre, promedio):
    """Objetivo por defecto de un tema (el docente puede editarlo en la propuesta)."""
    prom = f"{promedio:.2f}".replace(".", ",")
    return (
        f"Mejorar el desempeño en «{tema_nombre}» de {asignatura_nombre}, "
        f"llevando el promedio actual de {prom} a 7,00 o más."
    )


def objetivo_manual(tema_nombre, asignatura_nombre, motivo):
    """Objetivo por defecto de un tema de refuerzo manual (el docente puede editarlo)."""
    base = f"Reforzar «{tema_nombre}» de {asignatura_nombre}"
    motivo = (motivo or "").rstrip(" .")
    return f"{base}: {motivo}." if motivo else f"{base}."
