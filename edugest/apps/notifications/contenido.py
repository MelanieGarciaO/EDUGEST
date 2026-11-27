"""
Textos y datos comunes de los avisos sobre actividades (receptores de señales y comando de
recordatorios). Funciones puras: no envían nada.
"""

from collections import defaultdict

RUTA_ACTIVIDADES = "/representante/actividades"


def fecha(valor):
    return valor.strftime("%d/%m/%Y") if valor else ""


def entrega(actividad):
    texto = fecha(actividad.fecha_entrega)
    if actividad.hora_entrega and actividad.hora_entrega.strftime("%H:%M") != "00:00":
        texto += f" hasta las {actividad.hora_entrega.strftime('%H:%M')}"
    return texto


def resumen(texto, maximo=160):
    texto = " ".join((texto or "").split())
    return texto if len(texto) <= maximo else texto[: maximo - 1].rsplit(" ", 1)[0] + "…"


def estudiantes_por_representante(actividad):
    """
    {representante: [estudiantes]} de los estudiantes a los que va la actividad: todo el
    paralelo o, en una evaluación de refuerzo, solo los que completaron su plan.
    """
    grupos = defaultdict(list)
    for e in actividad.estudiantes_dirigidos().select_related("representante"):
        grupos[e.representante].append(e)
    return grupos


def nombres(estudiantes):
    primeros = [e.first_name.split()[0] for e in estudiantes]
    return primeros[0] if len(primeros) == 1 else ", ".join(primeros[:-1]) + " y " + primeros[-1]


def detalles_actividad(actividad):
    detalles = [
        ("Asignatura", actividad.asignacion.asignatura.nombre),
        ("Paralelo", actividad.asignacion.paralelo.nombre_completo),
        ("Entrega", entrega(actividad)),
    ]
    if actividad.tema:
        detalles.append(("Tema", actividad.tema))
    if actividad.materiales:
        detalles.append(("Materiales", ", ".join(actividad.materiales)))
    detalles.append(("Modalidad", actividad.get_modalidad_entrega_display()))
    return detalles
