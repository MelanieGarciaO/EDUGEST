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


# ---------------------------------------------------------------------------
# DUA dentro de cada fase del ciclo ERCA
# ---------------------------------------------------------------------------
# El ERCA ordena los momentos del aprendizaje y el DUA da flexibilidad DENTRO de cada uno.
# Cada fase lleva un apoyo propio, apoyado en el principio del DUA que más le corresponde:
#   Experiencia        -> Implicación (despertar el interés desde lo que vive)
#   Reflexión          -> Acción y expresión (que exprese lo que piensa como pueda)
#   Conceptualización  -> Representación (presentar el concepto de varias formas)
#   Aplicación         -> Acción y expresión (que demuestre lo aprendido de varias formas)
FASES = ("experiencia", "reflexion", "conceptualizacion", "aplicacion")
PRINCIPIO_FASE = {
    "experiencia": "Implicación",
    "reflexion": "Acción y expresión",
    "conceptualizacion": "Representación",
    "aplicacion": "Acción y expresión",
}

FASE_EXPERIENCIA = {
    "matematica": "Empezar con una situación real de casa donde aparezca «{tema}» (repartir comida, contar dinero, medir ingredientes) y dejarle elegir cuál usar.",
    "lengua": "Empezar con un cuento, una noticia o un tema que le guste y conversar sobre lo que ya sabe de «{tema}».",
    "ciencias": "Empezar observando algo real de la casa o del entorno relacionado con «{tema}» y preguntarle qué cree que pasa.",
    "sociales": "Empezar con una historia de la familia, el barrio o la ciudad relacionada con «{tema}».",
    "ingles": "Empezar con una canción, un juego u objetos de la casa para nombrar palabras de «{tema}».",
    "general": "Empezar con una situación de su vida diaria relacionada con «{tema}» y dejarle elegir por dónde comenzar.",
}
FASE_REFLEXION = (
    "Dejar que cuente lo que entendió y lo que le costó como prefiera: hablando, dibujando o escribiendo "
    "pocas palabras. Ayudarle con preguntas cortas: ¿qué hiciste?, ¿dónde te confundiste?, ¿qué harías distinto?"
)
FASE_CONCEPTUALIZACION = {
    "matematica": "Explicar «{tema}» primero con objetos o dibujos, luego con un ejemplo resuelto paso a paso y al final con números.",
    "lengua": "Explicar «{tema}» leyendo un ejemplo en voz alta, resaltando las palabras clave y armando un esquema sencillo.",
    "ciencias": "Explicar «{tema}» con imágenes, un esquema o un video corto, y aclarar las palabras nuevas con dibujos.",
    "sociales": "Explicar «{tema}» con un mapa, una línea de tiempo o fotografías.",
    "ingles": "Presentar las palabras de «{tema}» con imágenes, gestos y audio, repitiéndolas en voz alta.",
    "general": "Explicar «{tema}» combinando la explicación oral con imágenes, ejemplos y un esquema.",
}
FASE_APLICACION = {
    "matematica": "Practicar con ejercicios cortos y situaciones nuevas (compras, recetas, juegos); permitir que resuelva con material, con dibujos o explicando en voz alta.",
    "lengua": "Practicar con textos nuevos; aceptar respuestas orales, dibujos o resúmenes cortos además de las escritas.",
    "ciencias": "Aplicar lo aprendido a otra situación de la casa; puede mostrarlo con un dibujo, una maqueta sencilla o explicándolo.",
    "sociales": "Relacionar lo aprendido con otra situación cercana; puede mostrarlo con un organizador gráfico, un dibujo o una exposición corta.",
    "ingles": "Usar las palabras en un juego o un diálogo corto; valorar las respuestas orales y señalando imágenes.",
    "general": "Practicar en situaciones nuevas y dejar que demuestre lo aprendido como prefiera: oral, escrito, con dibujos o con material.",
}


def sugerir_fases(asignatura_nombre, tema_nombre, nivel_dificultad, reincidente=False, motivo=""):
    """Devuelve {"experiencia", "reflexion", "conceptualizacion", "aplicacion"}: un apoyo DUA por fase."""
    clave = _clave_asignatura(asignatura_nombre)
    datos = {"tema": tema_nombre}

    experiencia = [FASE_EXPERIENCIA[clave].format(**datos)]
    reflexion = [FASE_REFLEXION]
    conceptualizacion = [FASE_CONCEPTUALIZACION[clave].format(**datos)]
    aplicacion = [FASE_APLICACION[clave].format(**datos)]

    if nivel_dificultad == ALTA:
        experiencia.append("Que la actividad sea corta (15 a 20 minutos).")
        reflexion.append("Reconocer cada avance, aunque sea pequeño.")
        conceptualizacion.append("Presentar poca información a la vez y repetir el ejemplo con pequeñas variaciones.")
        aplicacion.append("Dejar un ejemplo modelo a la vista al inicio y retirarlo poco a poco.")
    if reincidente:
        experiencia.append("Recordar juntos qué le funcionó la vez anterior.")
        conceptualizacion.append("Probar una forma de explicación distinta a la que ya se usó.")
    if nivel_dificultad == MANUAL and motivo:
        aplicacion.append(f"Centrar la práctica en: {motivo.rstrip(' .')}.")

    return {
        "experiencia": " ".join(experiencia),
        "reflexion": " ".join(reflexion),
        "conceptualizacion": " ".join(conceptualizacion),
        "aplicacion": " ".join(aplicacion),
    }
