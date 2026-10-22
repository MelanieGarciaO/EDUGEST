"""
Escala de calificaciones y reglas para detectar dificultades. Son funciones puras (sin base
de datos) para poder probarlas y reutilizarlas.

Niveles cualitativos, según la escala del Reglamento General a la LOEI (sobre 10):
    9,00 - 10,00  Domina los aprendizajes
    7,00 -  8,99  Alcanza los aprendizajes
    4,01 -  6,99  Está próximo a alcanzar los aprendizajes
    0,00 -  4,00  No alcanza los aprendizajes

Regla de dificultad de EduGest (propuesta del proyecto, no norma): un estudiante tiene
dificultad en un tema cuando su promedio ahí es menor a 7,00.
"""

from decimal import ROUND_HALF_UP, Decimal

NOTA_MINIMA = Decimal("0")
NOTA_MAXIMA = Decimal("10")
UMBRAL_ALCANZA = Decimal("7.00")
UMBRAL_DOMINA = Decimal("9.00")
LIMITE_NO_ALCANZA = Decimal("4.00")

DOMINA = "DOMINA"
ALCANZA = "ALCANZA"
PROXIMO = "PROXIMO"
NO_ALCANZA = "NO_ALCANZA"

NOMBRES_NIVEL = {
    DOMINA: "Domina los aprendizajes",
    ALCANZA: "Alcanza los aprendizajes",
    PROXIMO: "Está próximo a alcanzar los aprendizajes",
    NO_ALCANZA: "No alcanza los aprendizajes",
}

MODERADA = "MODERADA"
ALTA = "ALTA"


def redondear(valor):
    """Redondea a dos decimales (mitad hacia arriba)."""
    return Decimal(valor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def promedio(valores):
    """Media simple redondeada a dos decimales; None si no hay valores."""
    valores = list(valores)
    if not valores:
        return None
    return redondear(sum(valores, Decimal("0")) / Decimal(len(valores)))


def nivel_cualitativo(valor):
    if valor is None:
        return None
    if valor >= UMBRAL_DOMINA:
        return DOMINA
    if valor >= UMBRAL_ALCANZA:
        return ALCANZA
    if valor > LIMITE_NO_ALCANZA:
        return PROXIMO
    return NO_ALCANZA


def nombre_nivel(nivel):
    return NOMBRES_NIVEL.get(nivel)


def nivel_dificultad(promedio_tema):
    """None si alcanza los aprendizajes; MODERADA (4,01-6,99) o ALTA (4,00 o menos)."""
    if promedio_tema is None or promedio_tema >= UMBRAL_ALCANZA:
        return None
    if promedio_tema <= LIMITE_NO_ALCANZA:
        return ALTA
    return MODERADA
