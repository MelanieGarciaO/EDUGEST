"""
Extracción de datos de una indicación docente escrita en lenguaje natural.

Del texto se proponen: asignatura, descripción de la actividad, fecha de entrega,
materiales y (si se menciona) el tema. Es una PROPUESTA: el docente siempre revisa y
corrige antes de publicar, y lo que no se pueda identificar se deja vacío.

Papel de cada herramienta:
- spaCy (modelo `es_core_news_sm`): tokenización y lematización del texto, usadas para
  reconocer la asignatura aunque se escriba en plural, con tildes o abreviada.
- Reglas y expresiones regulares: fechas (relativas y explícitas), materiales y limpieza
  de la descripción. El modelo de spaCy en español no reconoce fechas, por eso esta
  parte es propia.
- Respaldo ("fallback"): si el modelo de spaCy no está instalado, el motor sigue
  funcionando con una tokenización simple y devuelve `motor = "reglas"`.

Este módulo no depende de la base de datos: recibe las asignaturas candidatas como una
lista de pares (id, nombre) y la fecha de hoy.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

from django.conf import settings

logger = logging.getLogger(__name__)

MODELO_SPACY_POR_DEFECTO = "es_core_news_sm"
# Si una fecha sin año ya pasó, se asume el año siguiente solo cuando queda cerca
# (por ejemplo, diciembre -> enero). Si no, se deja tal cual y se advierte.
DIAS_MAX_CAMBIO_DE_ANIO = 90


# ---------------------------------------------------------------------------
# spaCy (carga perezosa con respaldo)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def obtener_nlp():
    """Devuelve el pipeline de spaCy o None si no está disponible (modo respaldo)."""
    nombre = getattr(settings, "PLN_SPACY_MODEL", MODELO_SPACY_POR_DEFECTO)
    if not nombre:
        return None
    try:
        import spacy

        return spacy.load(nombre, exclude=["ner", "parser"])
    except Exception as exc:  # modelo no instalado, spaCy ausente, etc.
        logger.warning("spaCy no disponible (%s); se usarán solo reglas.", exc)
        return None


# ---------------------------------------------------------------------------
# Normalización y tokenización
# ---------------------------------------------------------------------------
def _quitar_tildes(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _normalizar(palabra):
    """Minúsculas, sin tildes y sin marca de plural (aplicado igual a ambos lados)."""
    p = _quitar_tildes(palabra.lower())
    if len(p) > 4 and p.endswith("es") and p[-3] in "lrndz":
        return p[:-2]
    if len(p) > 3 and p.endswith("s"):
        return p[:-1]
    return p


@dataclass(frozen=True)
class Token:
    inicio: int
    fin: int
    norm: str
    lema: str


def _tokenizar(texto, nlp):
    tokens = []
    if nlp is not None:
        for t in nlp(texto):
            if t.is_space or not re.search(r"\w", t.text):
                continue
            tokens.append(
                Token(t.idx, t.idx + len(t.text), _normalizar(t.text), _normalizar(t.lemma_ or ""))
            )
    else:
        for m in re.finditer(r"\w+", texto):
            tokens.append(Token(m.start(), m.end(), _normalizar(m.group()), ""))
    return tokens


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------
def _solapa(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _sin_spans(texto, spans, desde=0, hasta=None):
    """Devuelve texto[desde:hasta] sin los tramos indicados (unidos por un espacio)."""
    hasta = len(texto) if hasta is None else hasta
    partes, pos = [], desde
    for ini, fin in sorted(spans):
        ini, fin = max(ini, desde), min(fin, hasta)
        if fin <= ini:
            continue
        if ini > pos:
            partes.append(texto[pos:ini])
        pos = max(pos, fin)
    if pos < hasta:
        partes.append(texto[pos:hasta])
    return " ".join(partes)


_RE_PREP_FINAL = re.compile(r"(?:\s+(?:de|del|en|para|y|e|el|la|con|a))+$", re.IGNORECASE)


def _limpiar(texto):
    t = " ".join(texto.split())
    t = re.sub(r"\s+([,;.:])", r"\1", t)
    t = re.sub(r"^[\s,;.:]+", "", t)
    t = re.sub(r"^(?:y|e)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"[\s,;:.]+$", "", t)
    t = _RE_PREP_FINAL.sub("", t)
    t = t.strip()
    return t[0].upper() + t[1:] if t else t


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_DIAS_SEMANA = {
    "lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3,
    "viernes": 4, "sabado": 5, "domingo": 6,
}
_NUMEROS = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7}

_MESES_RE = "|".join(_MESES)
_DIAS_RE = r"lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo"
_PREP = r"(?:(?:para|hasta|antes\s+del?|a\s+m[aá]s\s+tardar)\s+)?"
_PRE_FECHA = (
    _PREP
    + r"(?:(?:el|este)\s+)?(?:pr[oó]ximo\s+)?(?:d[ií]a\s+)?"
    + rf"(?:(?:{_DIAS_RE})\s*,?\s+)?(?:el\s+)?"
)
_FLAGS = re.IGNORECASE

_RE_FECHA_TEXTO = re.compile(
    rf"(?<!\w)(?P<pre>{_PRE_FECHA})(?P<d>\d{{1,2}})\s+de\s+(?P<mes>{_MESES_RE})"
    r"(?:\s+(?:de|del)\s+(?P<y>\d{4}))?(?!\w)",
    _FLAGS,
)
_RE_FECHA_NUM = re.compile(
    rf"(?<!\w)(?P<pre>{_PRE_FECHA})(?P<d>\d{{1,2}})(?P<s>[/-])(?P<m>\d{{1,2}})"
    r"(?:(?P=s)(?P<y>\d{2,4}))?(?![\d/-])",
    _FLAGS,
)
_RE_DIA_SOLO = re.compile(
    r"(?<!\w)(?:para|hasta|antes\s+del?)\s+el\s+(?P<d>\d{1,2})"
    r"(?!\s*(?:de\b|[/\-\d])|\s+[a-záéíóúñ]{3,})",
    _FLAGS,
)
_RE_PASADO_MANANA = re.compile(
    r"(?<!\w)(?:(?:para|hasta|antes\s+del?)\s+)?pasado\s+ma[ñn]ana(?!\w)", _FLAGS
)
_RE_MANANA = re.compile(
    r"(?<!\w)(?:(?:para|hasta|antes\s+del?)\s+)?(?<!la )(?<!esta )ma[ñn]ana(?!\w)", _FLAGS
)
_RE_HOY = re.compile(r"(?<!\w)(?:(?:para|hasta)\s+)?hoy(?!\w)", _FLAGS)
_RE_EN_N_DIAS = re.compile(
    r"(?<!\w)(?:para|dentro\s+de|en)\s+(?P<n>\d{1,2}|un|una|dos|tres|cuatro|cinco|seis|siete)"
    r"\s+(?P<u>d[ií]as?|semanas?)(?!\w)",
    _FLAGS,
)
_RE_DIA_SEMANA = re.compile(
    rf"(?<!\w){_PREP}(?:(?:el|este|esta)\s+)?(?:pr[oó]xim[oa]\s+)?(?P<dia>{_DIAS_RE})(?!\w)"
    r"(?:\s+pr[oó]ximo)?"
    r"(?P<sem>\s+(?:de|en)\s+la\s+(?:pr[oó]xima\s+semana|semana\s+pr[oó]xima|semana\s+que\s+viene))?",
    _FLAGS,
)
_RE_PRE_CON_PREP = re.compile(
    rf"(?:para|hasta|antes\s+del?|a\s+m[aá]s\s+tardar|(?:{_DIAS_RE}))", _FLAGS
)


def _fecha_con_anio(d, m, y, hoy):
    """Resuelve día/mes/año (año opcional). Devuelve None si la fecha no existe."""
    if y is None:
        try:
            f = date(hoy.year, m, d)
        except ValueError:
            return None
        if f < hoy:
            try:
                siguiente = date(hoy.year + 1, m, d)
            except ValueError:
                return f
            if (siguiente - hoy).days <= DIAS_MAX_CAMBIO_DE_ANIO:
                return siguiente
        return f
    y = int(y)
    if y < 100:
        y += 2000
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _proximo_dia_del_mes(d, hoy):
    y, m = hoy.year, hoy.month
    for _ in range(14):
        try:
            f = date(y, m, d)
        except ValueError:
            f = None
        if f is not None and f >= hoy:
            return f
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return None


def _dia_de_semana(nombre, hoy, proxima_semana):
    objetivo = _DIAS_SEMANA[_quitar_tildes(nombre.lower())]
    if proxima_semana:
        lunes_siguiente = hoy + timedelta(days=7 - hoy.weekday())
        return lunes_siguiente + timedelta(days=objetivo)
    delta = (objetivo - hoy.weekday()) % 7 or 7
    return hoy + timedelta(days=delta)


def _buscar_fecha(texto, hoy):
    """
    Devuelve (fecha, confianza, tramos_a_quitar, advertencias).
    Se elige la primera fecha mencionada en el texto; ante empate gana la más explícita.
    """
    candidatos = []  # (inicio, prioridad, fin, fecha, confianza)

    for m in _RE_FECHA_TEXTO.finditer(texto):
        f = _fecha_con_anio(int(m["d"]), _MESES[m["mes"].lower()], m["y"], hoy)
        if f:
            candidatos.append((m.start(), 1, m.end(), f, "alta"))

    for m in _RE_FECHA_NUM.finditer(texto):
        con_anio = m["y"] is not None
        if m["s"] == "-" and not con_anio:
            continue  # "pág. 10-12" no es una fecha
        if not con_anio and not _RE_PRE_CON_PREP.search(m["pre"]):
            continue  # "fracciones 3/4" no es una fecha
        dia, mes = int(m["d"]), int(m["m"])
        if not 1 <= mes <= 12:
            continue
        f = _fecha_con_anio(dia, mes, m["y"], hoy)
        if f:
            candidatos.append((m.start(), 1, m.end(), f, "alta"))

    for m in _RE_PASADO_MANANA.finditer(texto):
        candidatos.append((m.start(), 2, m.end(), hoy + timedelta(days=2), "alta"))
    for m in _RE_MANANA.finditer(texto):
        candidatos.append((m.start(), 2, m.end(), hoy + timedelta(days=1), "alta"))
    for m in _RE_HOY.finditer(texto):
        candidatos.append((m.start(), 2, m.end(), hoy, "alta"))

    for m in _RE_EN_N_DIAS.finditer(texto):
        n = int(m["n"]) if m["n"].isdigit() else _NUMEROS[m["n"].lower()]
        if m["u"].lower().startswith("semana"):
            n *= 7
        candidatos.append((m.start(), 2, m.end(), hoy + timedelta(days=n), "alta"))

    for m in _RE_DIA_SOLO.finditer(texto):
        f = _proximo_dia_del_mes(int(m["d"]), hoy)
        if f:
            candidatos.append((m.start(), 3, m.end(), f, "media"))

    for m in _RE_DIA_SEMANA.finditer(texto):
        f = _dia_de_semana(m["dia"], hoy, bool(m["sem"]))
        candidatos.append((m.start(), 3, m.end(), f, "media"))

    if not candidatos:
        return None, None, [], []

    elegido = min(candidatos, key=lambda c: (c[0], c[1], -(c[2] - c[0])))
    ini, _, fin, fecha, confianza = elegido
    span = (ini, fin)

    quitar = [span]
    distintas = False
    for c in candidatos:
        otro = (c[0], c[2])
        if c is elegido or _solapa(otro, span):
            continue
        if c[3] == fecha:
            quitar.append(otro)
        else:
            distintas = True

    advertencias = []
    if distintas:
        advertencias.append(
            "Se detectaron varias fechas; se tomó la primera. Revisa la fecha de entrega."
        )
    if fecha < hoy:
        advertencias.append(
            f"La fecha detectada ({fecha.strftime('%d/%m/%Y')}) ya pasó. Corrígela antes de publicar."
        )
    return fecha, confianza, quitar, advertencias


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------
_RE_MATERIALES = re.compile(
    r"(?<!\w)(?:(?:con\s+)?(?:los\s+)?(?:siguientes\s+)?materiales(?:\s+necesarios)?"
    r"|traer|traigan|trae|traerán|llevar|lleven)(?!\w)\s*:?\s*",
    _FLAGS,
)
_RE_ANTES_DE_MATERIALES = re.compile(
    r"(?:\s*[,;]|\s+y|\s+e)?\s*(?:(?:no\s+olviden|recuerden|por\s+favor|favor)\s*)?$",
    _FLAGS,
)
_RE_FIN_DE_LISTA = re.compile(r"\.(?:\s|$)")
_RE_SEPARADOR_ITEMS = re.compile(r"\s*(?:,|;|\s+y\s+|\s+e\s+)\s*", _FLAGS)
_RE_ARTICULO_INICIAL = re.compile(r"^(?:el|la|los|las|un|una|unos|unas|su|sus)\s+", _FLAGS)


def _buscar_materiales(texto, spans_fecha):
    """Devuelve (lista_de_materiales, tramo_a_quitar | None)."""
    m = _RE_MATERIALES.search(texto)
    if not m:
        return [], None

    fin_lista = len(texto)
    corte = _RE_FIN_DE_LISTA.search(texto, m.end())
    if corte:
        fin_lista = corte.start()

    segmento = _sin_spans(texto, spans_fecha, desde=m.end(), hasta=fin_lista)
    items, vistos = [], set()
    for crudo in _RE_SEPARADOR_ITEMS.split(segmento):
        item = _RE_ARTICULO_INICIAL.sub("", crudo.strip()).strip(" .,:;")
        clave = item.lower()
        if item and clave not in vistos:
            vistos.add(clave)
            items.append(item[:100])
    if not items:
        return [], None

    previo = _RE_ANTES_DE_MATERIALES.search(texto[: m.start()])
    inicio = previo.start() if previo else m.start()
    return items, (inicio, fin_lista)


# ---------------------------------------------------------------------------
# Asignatura
# ---------------------------------------------------------------------------
_PALABRAS_VACIAS = {"y", "e", "de", "del", "la", "el", "los", "las", "en"}
# Palabras que aparecen en varios nombres de asignatura y no identifican a ninguna sola.
_PALABRAS_GENERICAS = {"ciencia", "estudio", "educacion", "area", "materia", "asignatura"}
_RE_ANTES_DE_ASIGNATURA = re.compile(
    r"(?:\b(?:de|del|en|para|sobre)\s+)?(?:(?:la|el)\s+)?"
    r"(?:(?:asignatura|materia|[áa]rea)\s+(?:de\s+)?)?$",
    _FLAGS,
)


def _buscar_asignatura(texto, tokens, asignaturas, excluidos):
    """
    Devuelve (asignatura | None, advertencia | None) donde asignatura es
    (id, nombre, (inicio, fin), confianza). Si hay un ganador claro pero también se
    menciona otra asignatura de forma más débil, se elige el ganador con confianza
    "media" y se advierte; si dos asignaturas empatan, no se elige ninguna.
    """
    libres = [t for t in tokens if not any(_solapa((t.inicio, t.fin), e) for e in excluidos)]
    candidatos = []  # (puntaje, id, nombre, inicio, fin)

    for asig_id, nombre in asignaturas:
        clave = [
            _normalizar(w) for w in re.findall(r"\w+", nombre) if _normalizar(w) not in _PALABRAS_VACIAS
        ]
        if not clave:
            continue

        exactas = {w: [i for i, t in enumerate(libres) if t.norm == w or t.lema == w] for w in clave}
        prefijos = {
            w: [
                i for i, t in enumerate(libres)
                if len(t.norm) >= 4 and t.norm != w and w.startswith(t.norm)
            ]
            for w in clave
        }

        mejor = None
        # 1) Nombre completo, con las palabras cercanas entre sí.
        if all(exactas[w] for w in clave):
            for ancla in exactas[clave[0]]:
                elegidas = [ancla]
                for w in clave[1:]:
                    elegidas.append(min(exactas[w], key=lambda p: abs(p - ancla)))
                if max(elegidas) - min(elegidas) <= len(clave) + 1:
                    mejor = (2, min(elegidas), max(elegidas))
                    break
        # 2) Una palabra distintiva (exacta o abreviada, p. ej. "mate").
        if mejor is None:
            for w in clave:
                if w in _PALABRAS_GENERICAS:
                    continue
                pos = exactas[w] or prefijos[w]
                if pos:
                    mejor = (1, pos[0], pos[0])
                    break

        if mejor:
            puntaje, i, j = mejor
            candidatos.append((puntaje, asig_id, nombre, libres[i].inicio, libres[j].fin))

    if not candidatos:
        return None, None

    maximo = max(c[0] for c in candidatos)
    finalistas = [c for c in candidatos if c[0] == maximo]
    if len(finalistas) > 1:
        return None, "Se mencionan varias asignaturas; elige la correcta."

    puntaje, asig_id, nombre, ini, fin = finalistas[0]
    previo = _RE_ANTES_DE_ASIGNATURA.search(texto[:ini])
    if previo:
        ini = previo.start()

    confianza = "alta" if puntaje == 2 else "media"
    aviso = None
    otras = [c[2] for c in candidatos if c[1] != asig_id]
    if otras:
        confianza = "media"
        aviso = f"También se menciona {', '.join(otras)}; verifica la asignatura."
    return (asig_id, nombre, (ini, fin), confianza), aviso


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------
_RE_TEMA = re.compile(
    r"(?:del\s+tema|sobre\s+el\s+tema|(?<!\w)tema)\s*:?\s+(?P<t>[^.,;:]+)", _FLAGS
)


def _buscar_tema(descripcion):
    """Tema escrito de forma explícita: «tema: Fracciones», «sobre el tema …»."""
    m = _RE_TEMA.search(descripcion)
    if not m:
        return ""
    tema = _limpiar(m["t"])
    return tema[:150]


# Palabras que no cuentan al comparar con el catálogo de temas.
_VACIAS_TEMA = _PALABRAS_VACIAS | {"con", "a", "al", "para", "por", "sobre", "un", "una", "lo"}
# Palabras que, solas, no bastan para elegir un tema (aparecen en muchos nombres).
_GENERICAS_TEMA = {"tipo", "numero", "operacion", "texto", "parte", "clase", "nocion", "elemento"}


def _clave_tema(nombre):
    return {
        _normalizar(w) for w in re.findall(r"\w+", nombre) if _normalizar(w) not in _VACIAS_TEMA
    }


def _buscar_tema_catalogo(tokens, temas, asignatura_id, excluidos):
    """
    Reconoce el tema comparando la indicación con el catálogo de temas del grado
    (temas y subtemas registrados por el administrador).

    - temas: lista de (id, nombre, asignatura_id).
    - Coincidencia completa (todas las palabras del tema aparecen, por forma o lema;
      «fracciones» = «fracción») -> confianza alta. Gana el tema más específico (más
      palabras): «fracciones equivalentes» antes que «fracciones».
    - Coincidencia parcial (la mitad o más de las palabras, con alguna distintiva) ->
      confianza media.
    - Si la asignatura ya se reconoció, solo se buscan sus temas.
    Devuelve (id, nombre, asignatura_id, confianza) o None.
    """
    palabras = {
        p
        for t in tokens
        if not any(_solapa((t.inicio, t.fin), e) for e in excluidos)
        for p in (t.norm, t.lema)
        if p
    }
    if not palabras:
        return None

    candidatos = []  # (completo, n_palabras, cobertura, id, nombre, asignatura)
    for tema_id, nombre, asig_id in temas:
        if asignatura_id and asig_id != asignatura_id:
            continue
        clave = _clave_tema(nombre)
        if not clave:
            continue
        halladas = clave & palabras
        if not halladas:
            continue
        completo = halladas == clave
        if not completo:
            if len(halladas) / len(clave) < 0.5 or not (halladas - _GENERICAS_TEMA):
                continue
        candidatos.append((completo, len(halladas), len(halladas) / len(clave), tema_id, nombre, asig_id))

    if not candidatos:
        return None
    candidatos.sort(key=lambda c: (c[0], c[1], c[2]), reverse=True)
    mejor = candidatos[0]
    empatados = [c for c in candidatos if c[:3] == mejor[:3]]
    if len(empatados) > 1 and len({c[5] for c in empatados}) > 1:
        return None  # el mismo tema en varias asignaturas: no se adivina
    return mejor[3], mejor[4], mejor[5], "alta" if mejor[0] else "media"


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def extraer(texto, asignaturas, hoy, nlp=None, temas=None):
    """
    Procesa una indicación y devuelve un diccionario serializable con la propuesta.

    - texto: indicación del docente.
    - asignaturas: lista de (id, nombre) que el docente imparte en el paralelo elegido.
    - hoy: fecha actual (para resolver "mañana", "el lunes", etc.).
    - nlp: pipeline de spaCy (opcional; sin él se usa solo reglas).
    - temas: catálogo del grado como lista de (id, nombre, asignatura_id) (opcional).
    """
    texto = " ".join(texto.split())
    advertencias = []

    fecha, conf_fecha, spans_fecha, adv = _buscar_fecha(texto, hoy)
    advertencias.extend(adv)

    materiales, span_materiales = _buscar_materiales(texto, spans_fecha)

    excluidos = list(spans_fecha)
    if span_materiales:
        excluidos.append(span_materiales)
    tokens = _tokenizar(texto, nlp)
    encontrada, adv_asig = _buscar_asignatura(texto, tokens, asignaturas, excluidos)
    if adv_asig:
        advertencias.append(adv_asig)

    asignatura_id = asignatura_nombre = conf_asig = None
    span_asignatura = None
    if encontrada:
        asignatura_id, asignatura_nombre, span_asignatura, conf_asig = encontrada

    # Tema según el catálogo del grado. Si la asignatura no se nombró, el tema la indica
    # («fracciones» -> Matemática).
    tema_catalogo = None
    if temas:
        excl_tema = [span_materiales] if span_materiales else []
        tema_catalogo = _buscar_tema_catalogo(tokens, temas, asignatura_id, excl_tema)
        if tema_catalogo and not asignatura_id:
            nombres = dict(asignaturas)
            if tema_catalogo[2] in nombres:
                asignatura_id, asignatura_nombre = tema_catalogo[2], nombres[tema_catalogo[2]]
                conf_asig = "media"
                advertencias.append(
                    f"Se asignó {asignatura_nombre} por el tema «{tema_catalogo[1]}»."
                )

    if not asignatura_id and len(asignaturas) == 1:
        asignatura_id, asignatura_nombre = asignaturas[0]
        conf_asig = "media"
        advertencias.append(
            f"Se asignó {asignatura_nombre} por ser la única asignatura que impartes en este paralelo."
        )

    quitar = list(spans_fecha)
    if span_materiales:
        quitar.append(span_materiales)
    if span_asignatura:
        quitar.append(span_asignatura)
    descripcion = _limpiar(_sin_spans(texto, quitar))
    conf_desc = "alta"
    if not descripcion:
        descripcion = texto[:1].upper() + texto[1:]
        conf_desc = "baja"

    # Prioridad: tema explícito («tema: …») > tema del catálogo.
    tema = _buscar_tema(descripcion)
    conf_tema = "alta" if tema else None
    if tema and temas:
        # Si el tema explícito coincide con uno del catálogo, se usa el nombre oficial.
        oficial = _buscar_tema_catalogo(_tokenizar(tema, nlp), temas, asignatura_id, [])
        if oficial and oficial[3] == "alta":
            tema = oficial[1]
    elif tema_catalogo and (not asignatura_id or tema_catalogo[2] == asignatura_id):
        tema, conf_tema = tema_catalogo[1], tema_catalogo[3]

    resultado = {
        "asignatura": asignatura_id,
        "asignatura_nombre": asignatura_nombre,
        "descripcion": descripcion,
        "fecha_entrega": fecha.isoformat() if fecha else None,
        "materiales": materiales,
        "tema": tema,
        "confianza": {
            "asignatura": conf_asig,
            "descripcion": conf_desc,
            "fecha_entrega": conf_fecha,
            "materiales": "alta" if materiales else None,
            "tema": conf_tema,
        },
        "advertencias": advertencias,
        "motor": "spacy" if nlp is not None else "reglas",
    }
    resultado["campos_vacios"] = [
        campo
        for campo in ("asignatura", "fecha_entrega", "descripcion")
        if not resultado[campo]
    ]
    return resultado
