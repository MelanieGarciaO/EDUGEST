"""
Protección contra la inyección de fórmulas en los Excel que genera EduGest.

openpyxl guarda como FÓRMULA cualquier texto que empiece con «=». Si un nombre, una
observación o una descripción empieza así (p. ej. «=HYPERLINK(...)»), Excel lo ejecutaría al
abrir el archivo. EduGest nunca escribe fórmulas en celdas (las listas desplegables usan
validación de datos, no celdas), así que toda celda con fórmula se guarda como texto.
"""


def proteger_formulas(wb):
    """Convierte en texto toda celda que openpyxl haya marcado como fórmula. Devuelve el libro."""
    for ws in wb.worksheets:
        for fila in ws.iter_rows():
            for celda in fila:
                if celda.data_type == "f":
                    celda.data_type = "s"
    return wb
