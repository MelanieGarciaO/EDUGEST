"""
Exportación de un Reporte (ver datos.py) a PDF o Excel.

- PDF: reportlab (A4 horizontal), encabezado institucional, filtros aplicados, tablas con
  encabezado repetido en cada página y numeración «Página X de Y».
- Excel: openpyxl, una hoja por sección, con filtros automáticos y encabezado inmovilizado.
"""

import re
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

AZUL = "17406F"
AZUL_CLARO = "EAF1F8"
GRIS = "5B6B80"


def _institucion():
    return getattr(settings, "INSTITUCION_NOMBRE", "") or "EduGest"


def _texto(valor):
    if valor is None:
        return ""
    if isinstance(valor, Decimal):
        return f"{valor:.2f}".replace(".", ",")
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def nombre_archivo(reporte, formato):
    base = re.sub(r"[^a-z0-9]+", "_", reporte.clave.lower())
    return f"edugest_{base}_{reporte.generado_en:%Y%m%d_%H%M}.{formato}"


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
class _DocConTotal(SimpleDocTemplate):
    """Dibuja el pie «Página X de Y» (se construye dos veces para conocer el total)."""

    def __init__(self, *args, pie="", **kwargs):
        super().__init__(*args, **kwargs)
        self.pie = pie
        self.total_paginas = 0

    def handle_pageEnd(self):
        self.total_paginas = max(self.total_paginas, self.page)
        super().handle_pageEnd()


def _pie(total):
    def dibujar(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor(f"#{GRIS}"))
        ancho, _ = doc.pagesize
        canvas.drawString(doc.leftMargin + 6, 1 * cm, doc.pie)
        texto = f"Página {doc.page} de {total}" if total else f"Página {doc.page}"
        canvas.drawRightString(ancho - doc.rightMargin - 6, 1 * cm, texto)
        canvas.setStrokeColor(colors.HexColor(f"#{AZUL}"))
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin + 6, 1.4 * cm, ancho - doc.rightMargin - 6, 1.4 * cm)
        canvas.restoreState()

    return dibujar


def _anchos(columnas, ancho_util):
    """
    Reparte el ancho según los pesos, sin cortar palabras del encabezado: cada columna
    recibe al menos el ancho de su palabra más larga. Las tablas de 2-3 columnas no se
    estiran a toda la página.
    """
    minimos = [
        max(stringWidth(p, "Helvetica-Bold", 7.8) for p in titulo.split()) + 14 for titulo, _ in columnas
    ]
    pesos = [p for _, p in columnas]
    total = ancho_util if len(columnas) > 3 else min(ancho_util, 2.6 * cm * sum(pesos))
    libre = total - sum(minimos)
    if libre <= 0:
        return [total * m / sum(minimos) for m in minimos]
    # Primero se asegura el mínimo; el resto se reparte por peso.
    anchos = [max(m, total * p / sum(pesos)) for m, p in zip(minimos, pesos)]
    exceso = sum(anchos) - total
    if exceso > 0:
        holgura = [a - m for a, m in zip(anchos, minimos)]
        anchos = [a - exceso * h / sum(holgura) for a, h in zip(anchos, holgura)]
    return anchos


def _contenido_pdf(reporte, ancho_util):
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=base["Title"], fontSize=17, textColor=colors.HexColor(f"#{AZUL}"),
                            alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], fontSize=9, textColor=colors.HexColor(f"#{GRIS}"))
    h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=12, textColor=colors.HexColor(f"#{AZUL}"),
                        spaceBefore=10, spaceAfter=4)
    celda = ParagraphStyle("celda", parent=base["Normal"], fontSize=7.8, leading=9.5)
    cabecera = ParagraphStyle("cab", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")
    vacio = ParagraphStyle("vacio", parent=base["Italic"], fontSize=9, textColor=colors.HexColor(f"#{GRIS}"))

    elementos = [
        Paragraph(escape(_institucion()), sub),
        Paragraph(escape(reporte.titulo), titulo),
        Paragraph(escape(reporte.descripcion), sub),
        Spacer(1, 4),
    ]
    meta = [f"<b>{escape(k)}:</b> {escape(_texto(v))}" for k, v in reporte.filtros]
    meta.append(f"<b>Generado:</b> {reporte.generado_en:%d/%m/%Y %H:%M} por {escape(reporte.generado_por)}")
    elementos.append(Paragraph(" &nbsp;·&nbsp; ".join(meta), sub))

    for seccion in reporte.secciones:
        elementos.append(Paragraph(escape(seccion.titulo), h2))
        if not seccion.filas:
            elementos.append(Paragraph(escape(seccion.vacio), vacio))
            continue
        anchos = _anchos(seccion.columnas, ancho_util)
        datos = [[Paragraph(escape(c), cabecera) for c, _ in seccion.columnas]]
        datos += [[Paragraph(escape(_texto(v)), celda) for v in fila] for fila in seccion.filas]
        tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{AZUL}")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#C9D3DF")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        estilo += [
            ("BACKGROUND", (0, i), (-1, i), colors.HexColor(f"#{AZUL_CLARO}"))
            for i in range(2, len(datos), 2)
        ]
        tabla.setStyle(TableStyle(estilo))
        elementos.append(tabla)
        if seccion.nota:
            elementos.append(Paragraph(escape(seccion.nota), vacio))
    return elementos


def a_pdf(reporte):
    pie = f"{_institucion()} · Documento de seguimiento; no reemplaza el registro oficial de calificaciones."

    def construir(total):
        salida = BytesIO()
        doc = _DocConTotal(
            salida, pagesize=landscape(A4), pie=pie, title=reporte.titulo, author="EduGest",
            leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm, bottomMargin=1.8 * cm,
        )
        doc.build(_contenido_pdf(reporte, doc.width - 12), onFirstPage=_pie(total), onLaterPages=_pie(total))
        return salida.getvalue(), doc.total_paginas

    _, total = construir(0)  # primera pasada: contar páginas
    contenido, _ = construir(total)
    return contenido


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def _valor_excel(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    return valor


def _nombre_hoja(titulo, usados):
    nombre = re.sub(r"[\[\]:*?/\\]", "", titulo)[:31] or "Hoja"
    base, n = nombre, 2
    while nombre in usados:
        nombre = f"{base[:28]} {n}"
        n += 1
    usados.add(nombre)
    return nombre


def a_xlsx(reporte):
    wb = Workbook()
    wb.remove(wb.active)
    usados = set()
    cab_fill = PatternFill("solid", fgColor=AZUL)
    zebra = PatternFill("solid", fgColor=AZUL_CLARO)

    for seccion in reporte.secciones:
        ws = wb.create_sheet(_nombre_hoja(seccion.titulo, usados))
        ws["A1"] = f"{reporte.titulo} · {seccion.titulo}"
        ws["A1"].font = Font(bold=True, size=14, color=AZUL)
        ws["A2"] = _institucion()
        filtros = " · ".join(f"{k}: {_texto(v)}" for k, v in reporte.filtros)
        ws["A3"] = filtros or "Sin filtros"
        ws["A4"] = f"Generado el {reporte.generado_en:%d/%m/%Y %H:%M} por {reporte.generado_por}"
        for celda in ("A2", "A3", "A4"):
            ws[celda].font = Font(italic=True, color=GRIS)

        fila_cab = 6
        for col, (encabezado, _) in enumerate(seccion.columnas, start=1):
            c = ws.cell(row=fila_cab, column=col, value=encabezado)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = cab_fill
            c.alignment = Alignment(vertical="center", wrap_text=True)

        if not seccion.filas:
            ws.cell(row=fila_cab + 1, column=1, value=seccion.vacio).font = Font(italic=True, color=GRIS)

        for i, fila in enumerate(seccion.filas, start=fila_cab + 1):
            for col, valor in enumerate(fila, start=1):
                c = ws.cell(row=i, column=col, value=_valor_excel(valor))
                if isinstance(valor, Decimal):
                    c.number_format = "0.00"
                elif isinstance(valor, (date, datetime)):
                    c.number_format = "DD/MM/YYYY"
                if (i - fila_cab) % 2 == 0:
                    c.fill = zebra

        if seccion.nota:
            ws.cell(row=fila_cab + len(seccion.filas) + 2, column=1, value=seccion.nota).font = Font(italic=True)

        for col, (encabezado, _) in enumerate(seccion.columnas, start=1):
            largo = max([len(encabezado)] + [len(_texto(f[col - 1])) for f in seccion.filas[:500]])
            ws.column_dimensions[get_column_letter(col)].width = min(max(largo + 2, 10), 60)
        ws.freeze_panes = ws.cell(row=fila_cab + 1, column=1)
        if seccion.filas:
            ultima = get_column_letter(len(seccion.columnas))
            ws.auto_filter.ref = f"A{fila_cab}:{ultima}{fila_cab + len(seccion.filas)}"

    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


EXPORTADORES = {"pdf": a_pdf, "xlsx": a_xlsx}
