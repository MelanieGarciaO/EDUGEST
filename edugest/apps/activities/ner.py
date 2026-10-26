"""
Reconocimiento de entidades (NER) basado en reglas para las indicaciones del docente.

Con spaCy se usa un `EntityRuler` dentro del pipeline (componente «edugest_ruler»):
patrones por token sobre el atributo LOWER, con las variantes de cada palabra (singular,
plural, con y sin tildes). Sin spaCy, el mismo conjunto de patrones se compara token a
token, de modo que ambos caminos reconocen exactamente las mismas entidades.

Etiquetas:
- MATERIAL:   útiles escolares (tijera, goma, lápices de colores, papel brillante…).
- ASIGNATURA: alias de asignaturas que no aparecen en su nombre oficial
              («lenguaje» -> Lengua y Literatura, «gimnasia» -> Educación Física…).
              El id de la entidad es una palabra clave del nombre oficial.
"""

import re
import unicodedata
from dataclasses import dataclass

NOMBRE_COMPONENTE = "edugest_ruler"

# Útiles escolares frecuentes en EGB (en singular; las variantes se generan solas).
MATERIALES = [
    "tijera", "goma", "goma en barra", "pegamento", "silicón", "silicona", "regla",
    "escuadra", "graduador", "transportador", "compás", "lápiz", "lápiz de color",
    "crayón", "crayola", "marcador", "resaltador",
    "esfero", "borrador", "sacapuntas", "cartulina", "cartulina A4", "cartón",
    "papelógrafo", "papel bond", "papel brillante", "papel crepé", "papel periódico",
    "papel seda", "fómix", "foami", "hoja", "hoja cuadriculada", "hoja de cuadros",
    "hoja de líneas", "cuaderno", "libro", "texto escolar", "diccionario", "calculadora",
    "plastilina", "témpera", "acuarela", "pincel", "lana", "hilo", "aguja punta roma",
    "palillo", "paleta", "botella plástica", "revista", "periódico", "recorte", "imagen",
    "fotografía", "mandil", "ropa deportiva", "uniforme deportivo", "pelota", "cuerda",
    "flash memory", "memoria USB",
]

# Alias de asignaturas (no incluidos en el nombre oficial) -> palabra clave del nombre.
ALIAS_ASIGNATURA = {
    "lenguaje": "lengua",
    "ccnn": "natural",
    "eess": "social",
    "cívica": "social",
    "civismo": "social",
    "gimnasia": "fisica",
    "ed física": "fisica",
    "arte": "artistica",
    "artes": "artistica",
    "eca": "artistica",
    "english": "ingles",
}

# Palabras que no se pluralizan dentro de un material compuesto.
_FIJAS = {"de", "del", "en", "a4", "usb", "punta", "roma", "bond", "memory", "flash"}


def _sin_tildes(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


# Plurales que no siguen la regla general (cambian la tilde).
_PLURALES_ESPECIALES = {"imagen": "imágenes", "examen": "exámenes", "origen": "orígenes"}


def _plural(palabra):
    if palabra in _PLURALES_ESPECIALES:
        return _PLURALES_ESPECIALES[palabra]
    if palabra[-1] in "aeiouáéíóú":
        return palabra + "s"
    if palabra.endswith("z"):
        return palabra[:-1] + "ces"  # lápiz -> lápices
    # Aguda terminada en consonante pierde la tilde: compás -> compases, cartón -> cartones.
    return _sin_tildes(palabra) + "es" if _sin_tildes(palabra) != palabra else palabra + "es"


def _variantes(palabra):
    p = palabra.lower()
    formas = {p} if p in _FIJAS else {p, _plural(p)}
    return sorted(formas | {_sin_tildes(f) for f in formas})


def _patron(frase):
    return [{"LOWER": {"IN": _variantes(w)}} for w in re.findall(r"\w+", frase)]


def patrones():
    """Patrones para el EntityRuler de spaCy (y para el respaldo sin spaCy)."""
    pats = [
        {"label": "MATERIAL", "pattern": _patron(m), "id": m.lower()} for m in MATERIALES
    ]
    pats += [
        {"label": "ASIGNATURA", "pattern": _patron(alias), "id": clave}
        for alias, clave in ALIAS_ASIGNATURA.items()
    ]
    return pats


def agregar_a_pipeline(nlp):
    """Agrega el EntityRuler al pipeline de spaCy (una sola vez)."""
    if NOMBRE_COMPONENTE not in nlp.pipe_names:
        ruler = nlp.add_pipe(
            "entity_ruler", name=NOMBRE_COMPONENTE, config={"overwrite_ents": True}
        )
        ruler.add_patterns(patrones())
    return nlp


@dataclass(frozen=True)
class Entidad:
    etiqueta: str
    clave: str
    inicio: int
    fin: int
    texto: str


def _respaldo(texto):
    """Mismo algoritmo que el EntityRuler (gana el tramo más largo, luego el primero)."""
    tokens = [(m.start(), m.end(), m.group().lower()) for m in re.finditer(r"\w+", texto)]
    candidatos = []
    for p in patrones():
        conjuntos = [set(t["LOWER"]["IN"]) for t in p["pattern"]]
        n = len(conjuntos)
        for i in range(len(tokens) - n + 1):
            if all(tokens[i + k][2] in conjuntos[k] for k in range(n)):
                candidatos.append((i, i + n, p["label"], p["id"]))
    candidatos.sort(key=lambda c: (-(c[1] - c[0]), c[0]))
    usados, elegidos = set(), []
    for ini, fin, etiqueta, clave in candidatos:
        if usados.isdisjoint(range(ini, fin)):
            usados.update(range(ini, fin))
            a, b = tokens[ini][0], tokens[fin - 1][1]
            elegidos.append(Entidad(etiqueta, clave, a, b, texto[a:b]))
    return sorted(elegidos, key=lambda e: e.inicio)


def buscar(texto, nlp=None):
    """Entidades MATERIAL y ASIGNATURA del texto, ordenadas por posición."""
    if nlp is not None and NOMBRE_COMPONENTE in nlp.pipe_names:
        doc = nlp(texto)
        return [
            Entidad(e.label_, e.ent_id_, e.start_char, e.end_char, e.text)
            for e in doc.ents
            if e.label_ in ("MATERIAL", "ASIGNATURA")
        ]
    return _respaldo(texto)
