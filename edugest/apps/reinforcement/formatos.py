"""
Formato de los recursos: cómo se presenta la actividad (principio de REPRESENTACIÓN del DUA:
ofrecer la información por distintos canales).

Cada recurso del banco tiene uno o varios formatos. Se guardan como dato para:
- filtrar el banco («quiero un juego», «material concreto»),
- que el plan prefiera recursos de formatos DISTINTOS en cada tema (representación múltiple),
- mostrar en el plan y en los reportes qué formas de representación se usaron.

Si nadie los indica (recursos antiguos, semillas), se deducen del título y las instrucciones.
"""

import re
import unicodedata

from django.db import models


class FormatoRecurso(models.TextChoices):
    TEXTO = "TEXTO", "Texto o ficha"
    VISUAL = "VISUAL", "Imágenes o esquemas"
    AUDIO = "AUDIO", "Audio o lectura en voz alta"
    VIDEO = "VIDEO", "Video"
    MANIPULATIVO = "MANIPULATIVO", "Material concreto"
    JUEGO = "JUEGO", "Juego"
    DIGITAL = "DIGITAL", "Recurso digital interactivo"


MAX_FORMATOS = 4

# Palabras que delatan cada formato (sin tildes, en minúsculas).
_PISTAS = {
    FormatoRecurso.VIDEO: r"\bvideos?\b|\bvideotutorial|\bclip\b|\byoutube\b",
    FormatoRecurso.AUDIO: r"\baudios?\b|\bescuch\w*|\bcancion\w*|\bpodcast\b|\bgraba\w*|\bvoz alta\b|\bdictado\b",
    FormatoRecurso.JUEGO: r"\bjueg\w*|\bjuga\w*|\bbingo\b|\bloteria\b|\bdomino\b|\bmemoria\b|\bdados?\b|\bcartas?\b|\bnaipes?\b|\brompecabezas\b|\badivinanza\w*|\bcompetencia\b|\bconcurso\b",
    FormatoRecurso.MANIPULATIVO: (
        r"\bmaterial concreto\b|\bregletas?\b|\btiras? de (?:papel|cartulina)\b|\bfichas de colores\b|\bbloques\b"
        r"|\bplastilina\b|\bsemillas\b|\bpalitos\b|\bfrejoles\b|\bmonedas\b|\bbillet\w*|\babaco\b|\btapas?\b"
        r"|\brecort\w*|\bpleg\w*|\bmaqueta\w*|\bobjetos? de (?:la )?casa\b|\bmanipul\w*|\bmide\b|\bmedir\b"
    ),
    FormatoRecurso.VISUAL: (
        r"\bdibuj\w*|\bimagen\w*|\bilustra\w*|\besquema\w*|\bmapas?\b|\bgrafic\w*|\btabla\w*|\borganizador\w*"
        r"|\blinea de tiempo\b|\bcolore\w*|\bpinta\w*|\bfotos?\b|\bfotografia\w*|\bcuadro\w*|\bdiagrama\w*"
    ),
    FormatoRecurso.DIGITAL: r"\bcomputador\w*|\btablet\w*|\bcelular\w*|\bapp\b|\baplicacion\b|\bplataforma\b|\binteractiv\w*|\bsimulador\w*|\bgeogebra\b|\bkahoot\b|\bwordwall\b",
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def inferir(*textos):
    """Deduce los formatos de un recurso a partir de su título e instrucciones."""
    texto = _normalizar(" ".join(t or "" for t in textos))
    encontrados = [f.value for f, patron in _PISTAS.items() if re.search(patron, texto)]
    # Lo que se lee o se resuelve por escrito es «texto o ficha» si no hay otro canal claro.
    if not encontrados or re.search(r"\blee\b|\bleer\b|\blectura\b|\bficha\b|\bhoja\b|\bescrib\w*|\bresuelve\b", texto):
        encontrados.append(FormatoRecurso.TEXTO.value)
    orden = list(FormatoRecurso.values)
    return sorted(set(encontrados), key=orden.index)[:MAX_FORMATOS]


def limpiar(valores):
    """Deja solo formatos válidos, sin repetir, en el orden del catálogo."""
    validos = set(FormatoRecurso.values)
    vistos = {str(v).upper() for v in (valores or []) if str(v).upper() in validos}
    return [f for f in FormatoRecurso.values if f in vistos][:MAX_FORMATOS]


def etiquetas(valores):
    return [FormatoRecurso(v).label for v in valores if v in FormatoRecurso.values]


def completar_existentes(Recurso, Actividad):
    """
    Deduce los formatos de los recursos y actividades de plan que no los tienen.
    Recibe los modelos (sirve para la migración y para las pruebas).
    """
    for modelo in (Recurso, Actividad):
        for obj in modelo.objects.filter(formatos=[]).only("id", "titulo", "instrucciones", "formatos"):
            obj.formatos = inferir(obj.titulo, obj.instrucciones)
            obj.save(update_fields=["formatos"])
