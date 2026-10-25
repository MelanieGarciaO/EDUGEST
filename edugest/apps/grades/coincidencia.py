"""
Búsqueda de estudiantes por nombre dentro de la nómina del paralelo.

Se usa al importar notas desde un Excel cualquiera (mejora 12) o desde texto libre
(mejora 13). La nómina es un universo cerrado y pequeño, por eso no se usa el NER de
personas de spaCy (poco fiable con apellidos sueltos): cada nombre escrito se compara con
los nombres reales, token por token, tolerando:
- orden distinto («Pérez Luis» = «Luis Pérez»), tildes y mayúsculas;
- solo el apellido o solo el nombre («Vera»), si identifica a un único estudiante;
- errores de tipeo leves («Gomes» ~ «Gómez»).
"""

import re
import unicodedata
from difflib import SequenceMatcher

UMBRAL_TOKEN = 0.75  # similitud mínima de cada palabra escrita
UMBRAL_ALTA = 0.97   # sin errores de tipeo -> confianza alta
MARGEN = 0.04        # si dos estudiantes quedan tan cerca, es ambiguo


class NoEncontrado(Exception):
    pass


class Ambiguo(Exception):
    def __init__(self, nombres):
        super().__init__(nombres)
        self.nombres = nombres


def normalizar(texto):
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z\s]", " ", sin_tildes.lower())


def tokens(texto):
    return [t for t in normalizar(texto).split() if len(t) > 1]


class Nomina:
    def __init__(self, estudiantes):
        self.estudiantes = [(e.id, e.full_name, tokens(e.full_name)) for e in estudiantes]

    @staticmethod
    def _puntaje(escritos, reales):
        """Promedio de la mejor similitud de cada palabra escrita (0 si alguna no se parece)."""
        total = 0.0
        usados = set()
        for t in escritos:
            mejor, idx = 0.0, None
            for i, r in enumerate(reales):
                if i in usados:
                    continue
                s = 1.0 if t == r else SequenceMatcher(None, t, r).ratio()
                if s > mejor:
                    mejor, idx = s, i
            if mejor < UMBRAL_TOKEN:
                return 0.0
            usados.add(idx)
            total += mejor
        return total / len(escritos)

    def buscar(self, texto):
        """Devuelve (id, nombre, confianza «alta»|«media»). Lanza NoEncontrado o Ambiguo."""
        escritos = tokens(texto)
        if not escritos:
            raise NoEncontrado()
        puntajes = sorted(
            ((self._puntaje(escritos, reales), est_id, nombre) for est_id, nombre, reales in self.estudiantes),
            reverse=True,
        )
        puntajes = [p for p in puntajes if p[0] > 0]
        if not puntajes:
            raise NoEncontrado()
        mejor = puntajes[0]
        empatados = [p for p in puntajes if mejor[0] - p[0] <= MARGEN]
        if len(empatados) > 1:
            raise Ambiguo([p[2] for p in empatados])
        return mejor[1], mejor[2], "alta" if mejor[0] >= UMBRAL_ALTA else "media"


def mensaje_error(texto, exc):
    if isinstance(exc, Ambiguo):
        return f"«{texto}» coincide con {', '.join(exc.nombres)}; escribe el nombre completo."
    return f"«{texto}» no coincide con ningún estudiante del paralelo."
