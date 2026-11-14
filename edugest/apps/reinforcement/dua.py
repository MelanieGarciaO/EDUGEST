"""
Apoyos del Diseño Universal para el Aprendizaje (DUA) para cada tema del plan.

El DUA organiza los apoyos en tres principios (CAST; adoptados por el Minedec):
- Implicación: cómo motivar y mantener el interés del estudiante.
- Representación: cómo presentar el contenido de varias formas.
- Acción y expresión: cómo puede demostrar lo que aprendió.

Al generar el plan se prellenan con estas reglas según la asignatura, el nivel de la
dificultad, si es reincidente y el motivo del docente. El docente los revisa y edita en la
propuesta (o pide una sugerencia a la IA). Están redactados para que también los entienda
la familia, que los ve como «Cómo apoyar en casa».
"""

import unicodedata

from apps.grades import scale

ALTA = scale.ALTA
MANUAL = "MANUAL"


def _clave_asignatura(nombre):
    texto = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode().lower()
    for clave, palabras in (
        ("matematica", ("matematica",)),
        ("lengua", ("lengua", "literatura", "comunicacion")),
        ("ciencias", ("ciencias naturales", "ciencias")),
        ("sociales", ("sociales", "historia", "civica")),
        ("ingles", ("ingles", "english")),
    ):
        if any(p in texto for p in palabras):
            return clave
    return "general"


IMPLICACION = {
    "matematica": "Relacionar «{tema}» con situaciones cotidianas, como compras, recetas, repartos o juegos de mesa.",
    "lengua": "Partir de textos o temas que le interesen (cuentos, deportes, animales) y leer en un ambiente tranquilo.",
    "ciencias": "Empezar con una observación o un experimento sencillo en casa que despierte su curiosidad.",
    "sociales": "Vincular el tema con su familia, su barrio, su ciudad o fechas importantes que conoce.",
    "ingles": "Usar canciones, juegos y palabras de objetos cotidianos para practicar sin presión.",
    "general": "Relacionar «{tema}» con situaciones de su vida diaria y explicarle para qué le sirve.",
}
REPRESENTACION = {
    "matematica": "Usar material concreto (objetos, tiras de papel, regletas) y ejemplos resueltos paso a paso antes de pasar a los números.",
    "lengua": "Leer en voz alta juntos, resaltar palabras clave y usar organizadores gráficos (esquemas, cuadros).",
    "ciencias": "Apoyarse en imágenes, esquemas y videos cortos; explicar el vocabulario nuevo con dibujos.",
    "sociales": "Usar mapas, líneas de tiempo, fotografías y relatos cortos.",
    "ingles": "Acompañar cada palabra o frase con imágenes, gestos y audio; repetir en voz alta.",
    "general": "Combinar la explicación oral con imágenes, ejemplos y esquemas.",
}
ACCION = {
    "matematica": "Permitir que explique en voz alta cómo resolvió, que use material concreto o dibujos además de la escritura.",
    "lengua": "Aceptar respuestas orales, dibujos o resúmenes cortos, además de las respuestas escritas.",
    "ciencias": "Permitir que muestre lo aprendido con dibujos, maquetas sencillas o explicando un experimento.",
    "sociales": "Aceptar organizadores gráficos, dibujos, maquetas o una exposición oral corta.",
    "ingles": "Valorar respuestas orales, señalando imágenes o completando con palabras, no solo frases escritas.",
    "general": "Permitir que demuestre lo aprendido de distintas formas: oral, escrita, con dibujos o con material.",
}


def sugerir(asignatura_nombre, tema_nombre, nivel_dificultad, reincidente=False, motivo=""):
    """Devuelve {"implicacion", "representacion", "accion_expresion"} para un tema del plan."""
    clave = _clave_asignatura(asignatura_nombre)
    datos = {"tema": tema_nombre}

    implicacion = [IMPLICACION[clave].format(**datos), "Plantear metas cortas y reconocer cada avance."]
    representacion = [REPRESENTACION[clave].format(**datos)]
    accion = [ACCION[clave].format(**datos)]

    if nivel_dificultad == ALTA:
        implicacion.append("Trabajar en sesiones breves (15 a 20 minutos) con pausas.")
        representacion.append("Presentar poca información a la vez y repetir el ejemplo con pequeñas variaciones.")
        accion.append("Dar apoyos al inicio (lista de pasos, ejemplo modelo) y retirarlos poco a poco.")
    if reincidente:
        implicacion.append("Conversar sobre qué le funcionó antes y dejarle elegir el orden de las actividades.")
        representacion.append("Probar una forma de explicación distinta a la que ya se usó.")
    if nivel_dificultad == MANUAL and motivo:
        accion.append(f"Centrar la evidencia en: {motivo.rstrip(' .')}.")

    return {
        "implicacion": " ".join(implicacion),
        "representacion": " ".join(representacion),
        "accion_expresion": " ".join(accion),
    }
