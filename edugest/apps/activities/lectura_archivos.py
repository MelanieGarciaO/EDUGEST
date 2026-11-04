"""
Lectura de la indicación docente desde un archivo (PDF o imagen).

El PLN (nlp.py) trabaja solo con texto. Este módulo es la capa previa que convierte un
archivo en texto para que el docente lo revise y luego se procese con «previsualizar».

Estrategia:
- PDF digital (texto seleccionable): se extrae directamente con pdfplumber. Rápido y exacto.
- PDF escaneado (páginas sin texto): cada página se renderiza a imagen (pypdfium2, incluido
  con pdfplumber; no requiere Poppler) y se aplica OCR con Tesseract.
- Imagen (JPG, PNG, WEBP): se valida/limpia con archivos.limpiar_imagen y se aplica OCR.

El OCR depende del programa Tesseract instalado en el sistema (con el idioma «spa»). Si no
está disponible, los PDF digitales siguen funcionando y las imágenes devuelven un error claro.

Nada se guarda: el archivo se lee en memoria y solo se devuelve el texto propuesto.
"""

import logging
import re
from functools import lru_cache
from io import BytesIO

from django.conf import settings
from PIL import Image, ImageOps
from rest_framework.exceptions import ValidationError

from . import archivos

logger = logging.getLogger(__name__)

PDF_TEXTO = "pdf_texto"
PDF_OCR = "pdf_ocr"
IMAGEN_OCR = "imagen_ocr"

# Una página con menos caracteres útiles que esto se considera escaneada.
MIN_CARACTERES_PAGINA = 25
RESOLUCION_OCR = 200  # dpi al renderizar páginas escaneadas
LADO_MINIMO_OCR = 1000  # Tesseract reconoce mejor si la imagen no es muy pequeña


def _ajuste(nombre, defecto):
    return getattr(settings, nombre, defecto)


# ---------------------------------------------------------------------------
# Tesseract (opcional)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def ocr_disponible():
    """True si pytesseract y el programa Tesseract (con el idioma configurado) están instalados."""
    try:
        import pytesseract

        cmd = _ajuste("TESSERACT_CMD", "")
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        idiomas = set(pytesseract.get_languages(config=""))
        requeridos = set(_ajuste("PLN_OCR_IDIOMA", "spa").split("+"))
        if not requeridos <= idiomas:
            logger.warning("Tesseract sin el idioma %s (tiene: %s).", requeridos, idiomas)
            return False
        return True
    except Exception as exc:  # pytesseract ausente o Tesseract no instalado
        logger.warning("OCR no disponible (%s).", exc)
        return False


def _ocr(imagen):
    import pytesseract

    imagen = ImageOps.grayscale(imagen)
    if max(imagen.size) < LADO_MINIMO_OCR:
        escala = LADO_MINIMO_OCR / max(imagen.size)
        imagen = imagen.resize((round(imagen.width * escala), round(imagen.height * escala)))
    return pytesseract.image_to_string(
        imagen, lang=_ajuste("PLN_OCR_IDIOMA", "spa"), config="--psm 6",
        timeout=_ajuste("PLN_OCR_TIMEOUT", 30),
    )


def _exigir_ocr():
    if not ocr_disponible():
        raise ValidationError(
            {"archivo": "El reconocimiento de texto en imágenes no está disponible en el "
                        "servidor. Sube un PDF con texto seleccionable o escribe la indicación."}
        )


# ---------------------------------------------------------------------------
# Limpieza del texto
# ---------------------------------------------------------------------------
def limpiar_texto(texto):
    """Une palabras cortadas con guion al final de línea, quita ruido y espacios repetidos."""
    texto = texto.replace("\x0c", "\n").replace("\u00ad", "")
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)  # «activi-\ndad» -> «actividad»
    lineas = []
    for linea in texto.splitlines():
        linea = re.sub(r"[ \t]+", " ", linea).strip()
        # Descarta líneas de puro ruido del OCR («|», «~~», «.,.»).
        if linea and re.search(r"[A-Za-zÁÉÍÓÚÑáéíóúñ0-9]", linea):
            lineas.append(linea)
    texto = "\n".join(lineas)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


# ---------------------------------------------------------------------------
# Extracción
# ---------------------------------------------------------------------------
def _leer_pdf(contenido):
    import pdfplumber

    max_paginas = _ajuste("PLN_ARCHIVO_MAX_PAGINAS", 5)
    advertencias, partes, metodo = [], [], PDF_TEXTO
    try:
        pdf = pdfplumber.open(BytesIO(contenido))
    except Exception:
        raise ValidationError({"archivo": "No se pudo leer el PDF."}) from None

    with pdf:
        total = len(pdf.pages)
        if total > max_paginas:
            advertencias.append(f"Solo se leyeron las primeras {max_paginas} de {total} páginas.")
        for pagina in pdf.pages[:max_paginas]:
            texto = pagina.extract_text() or ""
            if len(re.sub(r"\W", "", texto)) >= MIN_CARACTERES_PAGINA:
                partes.append(texto)
                continue
            # Página escaneada: OCR sobre la imagen de la página.
            _exigir_ocr()
            metodo = PDF_OCR
            imagen = pagina.to_image(resolution=RESOLUCION_OCR).original
            partes.append(_ocr(imagen))
    return "\n\n".join(partes), metodo, min(total, max_paginas), advertencias


def _leer_imagen(archivo, maximo_mb):
    _exigir_ocr()
    jpeg = archivos.limpiar_imagen(archivo, maximo_mb)  # valida formato y quita EXIF
    with Image.open(BytesIO(jpeg)) as imagen:
        return _ocr(imagen), IMAGEN_OCR, 1, []


def extraer_texto(archivo, max_caracteres):
    """
    Devuelve un dict con: texto, metodo (pdf_texto | pdf_ocr | imagen_ocr), paginas,
    advertencias. Lanza ValidationError si el archivo no es válido o no tiene texto.
    """
    maximo_mb = _ajuste("PLN_ARCHIVO_MAX_MB", 10)
    if archivo and archivos.es_pdf(archivo):
        contenido = archivos.validar_pdf(archivo, maximo_mb)
        texto, metodo, paginas, advertencias = _leer_pdf(contenido)
    else:
        if not archivo:
            raise ValidationError({"archivo": "Adjunta un archivo."})
        texto, metodo, paginas, advertencias = _leer_imagen(archivo, maximo_mb)

    texto = limpiar_texto(texto)
    if len(texto) < 3:
        raise ValidationError(
            {"archivo": "No se encontró texto legible en el archivo. Prueba con una foto más "
                        "nítida o escribe la indicación."}
        )
    if metodo != PDF_TEXTO:
        advertencias.append(
            "El texto se obtuvo por reconocimiento de imagen (OCR) y puede tener errores. Revísalo."
        )
    if len(texto) > max_caracteres:
        texto = texto[:max_caracteres].rsplit(" ", 1)[0]
        advertencias.append(f"El texto se recortó a {max_caracteres} caracteres.")
    return {"texto": texto, "metodo": metodo, "paginas": paginas, "advertencias": advertencias}
