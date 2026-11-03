"""
Validación y limpieza de archivos que suben los usuarios (imágenes y PDF).

Se usa en:
- Adjuntos del docente en una actividad (solo PDF: instrucciones, rúbrica, taller).
- Entregas del representante en actividades «desde la app» (imágenes o PDF).
- Evidencias de los planes de refuerzo (imágenes; ver reinforcement/evidencias.py).

Todo se guarda en el almacenamiento privado «evidencias» (bucket de Supabase o carpeta
local fuera de MEDIA_ROOT) y solo se entrega por la API, con autenticación.
"""

import re
import unicodedata
from io import BytesIO

from django.core.files.storage import storages
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

FORMATOS_IMAGEN = {"JPEG", "PNG", "WEBP"}
LADO_MAXIMO = 1600
CALIDAD = 82
Image.MAX_IMAGE_PIXELS = 40_000_000  # evita «bombas» de descompresión

IMAGEN = "IMAGEN"
PDF = "PDF"


def almacen():
    return storages["evidencias"]


def nombre_seguro(nombre, extension):
    """Nombre legible para mostrar/descargar (sin rutas ni caracteres raros)."""
    base = (nombre or "archivo").replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^\w\- ]+", "", base).strip()[:80] or "archivo"
    return f"{base}.{extension}"


def _validar_tamano(archivo, maximo_mb, campo="archivo"):
    if not archivo:
        raise ValidationError({campo: "Adjunta un archivo."})
    if archivo.size > maximo_mb * 1024 * 1024:
        raise ValidationError({campo: f"El archivo supera los {maximo_mb} MB."})


def es_pdf(archivo):
    archivo.seek(0)
    cabecera = archivo.read(1024)
    archivo.seek(0)
    return b"%PDF-" in cabecera[:1024]


def validar_pdf(archivo, maximo_mb, campo="archivo"):
    """Comprueba que sea un PDF real (firma %PDF y fin %%EOF) y devuelve sus bytes."""
    _validar_tamano(archivo, maximo_mb, campo)
    if not es_pdf(archivo):
        raise ValidationError({campo: "El archivo no es un PDF válido."})
    contenido = archivo.read()
    if b"%%EOF" not in contenido[-2048:]:
        raise ValidationError({campo: "El PDF está incompleto o dañado."})
    if b"/Encrypt" in contenido:
        raise ValidationError({campo: "El PDF está protegido con contraseña. Súbelo sin protección."})
    return contenido


def limpiar_imagen(archivo, maximo_mb, campo="archivo"):
    """
    Valida la imagen y la re-codifica a JPEG: elimina metadatos EXIF (incluida la
    ubicación GPS) y la reduce a 1600 px como máximo. Devuelve los bytes JPEG.
    """
    _validar_tamano(archivo, maximo_mb, campo)
    try:
        archivo.seek(0)
        with Image.open(archivo) as prueba:
            formato = prueba.format
            prueba.verify()
        archivo.seek(0)
        with Image.open(archivo) as img:
            img.load()
            if formato not in FORMATOS_IMAGEN:
                raise ValidationError({campo: "Formato no admitido. Usa JPG, PNG o WEBP."})
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = BytesIO()
            img.save(salida, format="JPEG", quality=CALIDAD, optimize=True)  # sin exif=
            return salida.getvalue()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ValidationError({campo: "El archivo no es una imagen válida."}) from None


def procesar_imagen_o_pdf(archivo, maximo_mb, campo="archivo"):
    """Devuelve (tipo, bytes, extensión). El tipo se decide por el contenido, no por el nombre."""
    _validar_tamano(archivo, maximo_mb, campo)
    if es_pdf(archivo):
        return PDF, validar_pdf(archivo, maximo_mb, campo), "pdf"
    return IMAGEN, limpiar_imagen(archivo, maximo_mb, campo), "jpg"
