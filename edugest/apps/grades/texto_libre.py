"""
Notas desde texto libre (mejora 13).

El docente pega sus apuntes, por ejemplo:
    «Vera 9, Gómez 4,5, Morales 7»   o una nota por línea («Luis Pérez: 8.5»).
Se extraen los pares nombre–nota y cada nombre se busca en la nómina del paralelo
(ver coincidencia.py). Como en el Excel, el resultado es una VISTA PREVIA: no se guarda
nada hasta que el docente revisa y pulsa «Guardar notas».
"""

import re
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .coincidencia import Ambiguo, Nomina, NoEncontrado, mensaje_error

LARGO_MAXIMO = 5000

# Nombre (letras, espacios, apóstrofos o guiones) seguido de una nota de 0 a 10.
# La nota acepta coma o punto decimal («4,5», «8.75») y separadores «:», «=», «-».
_RE_PAR = re.compile(
    r"(?P<nombre>[^\W\d_][^\W\d_'’\- ]*(?:[ '’\-]+[^\W\d_]+)*)"
    r"\s*[:=\-–]?\s*"
    r"(?P<nota>\d{1,2}(?:[.,]\d{1,2})?)(?![\d.,]\d)",
)


def interpretar(texto, estudiantes):
    if not texto or not texto.strip():
        raise ValidationError({"texto": "Pega las notas, por ejemplo: «Vera 9, Gómez 4,5»."})
    if len(texto) > LARGO_MAXIMO:
        raise ValidationError({"texto": f"El texto supera los {LARGO_MAXIMO} caracteres."})

    nomina = Nomina(estudiantes)
    filas, errores, vistos = [], [], {}
    for m in _RE_PAR.finditer(texto):
        nombre = re.sub(r"^(?:y|e)\s+", "", m["nombre"].strip(), flags=re.IGNORECASE)
        nota_txt = m["nota"]
        original = f"{nombre} {nota_txt}"
        nota = Decimal(nota_txt.replace(",", "."))
        if not Decimal("0") <= nota <= Decimal("10"):
            errores.append({"fila": None, "mensaje": f"«{original}»: la nota debe estar entre 0 y 10."})
            continue
        try:
            est_id, est_nombre, confianza = nomina.buscar(nombre)
        except (Ambiguo, NoEncontrado) as exc:
            errores.append({"fila": None, "mensaje": mensaje_error(nombre, exc)})
            continue
        if est_id in vistos:
            errores.append(
                {"fila": None, "mensaje": f"«{original}»: {est_nombre} ya tenía nota («{vistos[est_id]}»)."}
            )
            continue
        vistos[est_id] = original
        filas.append(
            {
                "estudiante": est_id,
                "estudiante_nombre": est_nombre,
                "valor": str(nota.quantize(Decimal("0.01"))),
                "confianza": confianza,
                "texto_original": original,
            }
        )

    if not filas and not errores:
        raise ValidationError(
            {"texto": "No se encontraron pares nombre–nota. Ejemplo: «Vera 9, Gómez 4,5»."}
        )
    return {"modo": "texto", "filas": filas, "errores": errores, "sin_nota": 0}
