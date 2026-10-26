"""
Resumen del desempeño en lenguaje claro (pensado para la familia).

Traduce promedios, niveles y dificultades a frases sencillas, sin números técnicos de
más ni siglas. Usa plantillas fijas (no IA generativa): el resultado es predecible,
verificable y siempre coherente con los datos registrados.
"""

from . import scale

# Cómo va el estudiante según el nivel cualitativo (LOEI).
_COMO_VA = {
    "DOMINA": "tiene un desempeño excelente",
    "ALCANZA": "va bien y alcanza lo esperado",
    "PROXIMO": "está cerca de lograr lo esperado, pero necesita apoyo",
    "NO_ALCANZA": "necesita apoyo para alcanzar lo esperado",
}


def _lista(nombres):
    """«a», «a y b», «a, b y c»."""
    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def _nota(valor):
    return f"{valor:.2f}".replace(".", ",")


def _recorrer(temas):
    for t in temas:
        yield t
        yield from _recorrer(t.get("subtemas", []))


def resumen_claro(nombre, asignaturas, promedio_general):
    """
    - nombre: nombre de pila del estudiante.
    - asignaturas: lista del desempeño (con sus temas y subtemas).
    - promedio_general: Decimal o None.
    Devuelve un dict con frases listas para mostrar (o None si no hay notas).
    """
    if promedio_general is None or not asignaturas:
        return None

    nivel = scale.nivel_cualitativo(promedio_general)
    general = f"En general, {nombre} {_COMO_VA[nivel]} (promedio {_nota(promedio_general)} de 10)."

    por_asignatura = [
        f"En {a['nombre']} {_COMO_VA[a['nivel']]}."
        for a in asignaturas
        if a.get("nivel")
    ]

    fortalezas, a_reforzar, superados = [], [], []
    for a in asignaturas:
        for t in _recorrer(a["temas"]):
            d = t.get("dificultad")
            if d and d["estado"] == "DETECTADA":
                if d.get("reincidente"):
                    a_reforzar.append(
                        f"{t['nombre']} ({a['nombre']}): ya lo había superado y volvió a "
                        "tener dificultad; conviene repasarlo en casa."
                    )
                elif d["nivel"] == "ALTA":
                    a_reforzar.append(
                        f"{t['nombre']} ({a['nombre']}): le está costando bastante; necesita "
                        "acompañamiento diario."
                    )
                else:
                    a_reforzar.append(
                        f"{t['nombre']} ({a['nombre']}): le falta poco; un repaso corto le ayudará."
                    )
            elif d and d["estado"] == "SUPERADA":
                superados.append(t["nombre"])
            elif t.get("nivel") == "DOMINA":
                fortalezas.append(t["nombre"])

    recomendacion = None
    if a_reforzar:
        recomendacion = (
            "Revise el plan de refuerzo en la sección «Planes de refuerzo» y acompañe a "
            f"{nombre} en las actividades marcadas."
        )
    elif nivel in ("DOMINA", "ALCANZA"):
        recomendacion = f"Siga motivando a {nombre}: mantener la rutina de estudio le está dando resultados."

    return {
        "general": general,
        "asignaturas": por_asignatura,
        "fortalezas": f"Domina muy bien: {_lista(fortalezas)}." if fortalezas else None,
        "a_reforzar": a_reforzar,
        "superados": (
            f"Superó las dificultades que tenía en: {_lista(superados)}." if superados else None
        ),
        "recomendacion": recomendacion,
    }
