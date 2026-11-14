"""
Ciclo de aprendizaje ERCA en los planes de refuerzo (Experiencia, Reflexión,
Conceptualización y Aplicación), según el enfoque pedagógico del Ministerio de Educación.

Cada actividad del plan pertenece a UNA fase. Al generar el plan:

1. Si el recurso del banco ya tiene fase, se respeta.
2. Si no, se asigna por regla según su nivel (el banco se elige básicas primero):
       primer recurso BÁSICO            -> Experiencia
       demás recursos BÁSICOS           -> Conceptualización
       recursos INTERMEDIOS/AVANZADOS   -> Aplicación; pero si aún no hay Conceptualización
                                           y hay 2 o más, el primero va a Conceptualización
3. Si al tema le falta alguna fase (casi siempre la Reflexión), se agrega una
   «actividad guía» corta de esa fase, para que cada tema recorra el ciclo completo.

El docente puede cambiar la fase de cualquier actividad mientras el plan es una propuesta.
"""

from .models import ORDEN_FASES, FaseErca, NivelActividad

F = FaseErca

DESCRIPCION = {
    F.EXPERIENCIA: "Parte de algo que el estudiante ya vive o conoce.",
    F.REFLEXION: "Piensa sobre lo que hizo: qué entendió y dónde se equivocó.",
    F.CONCEPTUALIZACION: "Aprende o repasa el concepto y sus pasos.",
    F.APLICACION: "Practica y usa lo aprendido en ejercicios o situaciones nuevas.",
}

# Actividades guía (se usan solo si al tema le falta esa fase).
GUIAS = {
    F.EXPERIENCIA: (
        "Encuentro «{tema}» en mi día a día",
        "1. Con ayuda de tu familia, busca en casa, en la tienda o en la escuela una situación "
        "donde aparezca «{tema}».\n2. Descríbela o dibújala en tu cuaderno.\n"
        "3. Cuenta a alguien de tu familia qué tiene que ver con lo que estás aprendiendo en {asignatura}.",
    ),
    F.REFLEXION: (
        "¿Qué sé y qué me cuesta de «{tema}»?",
        "1. Revisa tus trabajos anteriores de «{tema}».\n2. Responde en tu cuaderno: ¿Qué parte "
        "entendí bien? ¿En qué me equivoqué y por qué? ¿Qué pregunta le haría a mi docente?\n"
        "3. Conversa tus respuestas con tu familia.",
    ),
    F.CONCEPTUALIZACION: (
        "Aprendo los pasos de «{tema}»",
        "1. Lee la explicación de «{tema}» en tu libro o cuaderno de {asignatura}.\n2. Escribe con "
        "tus palabras las ideas o pasos más importantes.\n3. Resuelve un ejemplo guiado y compáralo "
        "con la explicación.",
    ),
    F.APLICACION: (
        "Practico «{tema}»",
        "1. Resuelve los ejercicios de «{tema}» que te indique tu docente.\n2. Revisa tus respuestas "
        "con calma.\n3. Explica a alguien de tu familia cómo resolviste uno de ellos.",
    ),
}
DURACION_GUIA = 15


def fase_por_nivel(nivel, hay_conceptualizacion=True, quedan_intermedios=1):
    """Fase sugerida para un recurso sin fase cuando se agrega uno por uno."""
    if nivel == NivelActividad.BASICO:
        return F.CONCEPTUALIZACION
    if not hay_conceptualizacion and quedan_intermedios >= 2:
        return F.CONCEPTUALIZACION
    return F.APLICACION


def asignar_fases(recursos):
    """Devuelve [(recurso, fase)] respetando la fase del banco y aplicando las reglas al resto."""
    fases = [r.fase or None for r in recursos]
    usadas = {f for f in fases if f}

    basicos = [i for i, r in enumerate(recursos) if not fases[i] and r.nivel == NivelActividad.BASICO]
    otros = [i for i, r in enumerate(recursos) if not fases[i] and r.nivel != NivelActividad.BASICO]

    for posicion, i in enumerate(basicos):
        fases[i] = F.EXPERIENCIA if posicion == 0 and F.EXPERIENCIA not in usadas else F.CONCEPTUALIZACION
        usadas.add(fases[i])
    for posicion, i in enumerate(otros):
        if posicion == 0 and F.CONCEPTUALIZACION not in usadas and len(otros) >= 2:
            fases[i] = F.CONCEPTUALIZACION
        else:
            fases[i] = F.APLICACION
        usadas.add(fases[i])
    return list(zip(recursos, fases))


def fases_faltantes(fases):
    presentes = set(fases)
    return [f for f in FaseErca.values if f not in presentes]


def guia(fase, tema_nombre, asignatura_nombre):
    titulo, instrucciones = GUIAS[fase]
    datos = {"tema": tema_nombre, "asignatura": asignatura_nombre}
    return titulo.format(**datos), instrucciones.format(**datos)


def ordenar(items, fase_de):
    """Ordena por fase ERCA conservando el orden original dentro de cada fase."""
    return sorted(items, key=lambda x: ORDEN_FASES.get(fase_de(x), len(ORDEN_FASES)))
