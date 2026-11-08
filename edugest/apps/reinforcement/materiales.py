"""
Material de referencia del docente para generar recursos con IA (diapositivas, guías, fotos).

Lógica:
- PPTX, DOCX, TXT/MD y PDF con texto -> se extrae el TEXTO en el servidor y se envía a la IA.
  (Gemini no lee PPTX/DOCX directamente, y el texto permite controlar tamaño y datos personales.)
- PDF escaneado (sin texto) e imágenes -> se envían como ARCHIVO a Gemini, que los lee
  (multimodal). Las imágenes se re-codifican sin metadatos EXIF.
- Nada se guarda: los archivos se procesan en memoria y se descartan.
- Datos personales: correos, cédulas y teléfonos del texto extraído se reemplazan por
  «[dato omitido]» antes de enviarlo (el plan gratuito de Gemini puede usar las solicitudes).
- Inyección de instrucciones: el material se envía delimitado como CONTENIDO de referencia y
  la instrucción de sistema ordena ignorar cualquier orden que aparezca dentro de él.
"""

import re
import zipfile
from dataclasses import dataclass, field
from io import BytesIO

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.activities import archivos

CAMPO = "materiales"
EXTENSIONES = (".pdf", ".pptx", ".docx", ".txt", ".md", ".jpg", ".jpeg", ".png", ".webp")
MAX_DESCOMPRIMIDO = 60 * 1024 * 1024  # protección contra «zip bombs» en PPTX/DOCX
MIN_TEXTO_PAGINA = 25

_CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# Cédula (10 dígitos, empieza por 0-2), RUC (13), celular 09XXXXXXXX y +593. No toca números
# escritos con espacios de miles («1 000 000 000»), comunes en clases de matemática.
_IDENTIFICACION = re.compile(r"(?<!\d)(?<!\d[.,])(?:\+593[\s-]?\d{8,9}|[0-2]\d{9}(?:\d{3})?)(?!\d)(?![.,]\d)")


def _ajuste(nombre, defecto):
    return getattr(settings, nombre, defecto)


def max_archivos():
    return _ajuste("IA_MATERIAL_MAX_ARCHIVOS", 3)


def max_mb():
    return _ajuste("IA_MATERIAL_MAX_MB", 10)


def max_caracteres():
    return _ajuste("IA_MATERIAL_MAX_CARACTERES", 15000)


def max_paginas():
    return _ajuste("IA_MATERIAL_MAX_PAGINAS", 30)


@dataclass
class Material:
    textos: list = field(default_factory=list)  # [(nombre, texto)]
    adjuntos: list = field(default_factory=list)  # [(nombre, mime, bytes)] para enviar a Gemini
    advertencias: list = field(default_factory=list)
    nombres: list = field(default_factory=list)

    @property
    def vacio(self):
        return not self.textos and not self.adjuntos


# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------
def anonimizar(texto):
    """Reemplaza correos y números de identificación/teléfono. Devuelve (texto, cuántos)."""
    texto, n1 = _CORREO.subn("[dato omitido]", texto)
    texto, n2 = _IDENTIFICACION.subn("[dato omitido]", texto)
    return texto, n1 + n2


def _normalizar(texto):
    texto = texto.replace("\x0c", "\n").replace("\u00ad", "")
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)
    lineas = [re.sub(r"[ \t]+", " ", l).strip() for l in texto.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(l for l in lineas if l)).strip()


# ---------------------------------------------------------------------------
# Extractores
# ---------------------------------------------------------------------------
def _zip_seguro(contenido, nombre):
    try:
        with zipfile.ZipFile(BytesIO(contenido)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_DESCOMPRIMIDO:
                raise ValidationError({CAMPO: f"«{nombre}» es demasiado grande al descomprimirse."})
            return z.namelist()
    except zipfile.BadZipFile:
        raise ValidationError({CAMPO: f"«{nombre}» está dañado o no es un archivo de Office válido."}) from None


def _texto_pptx(contenido, nombre, advertencias):
    from pptx import Presentation

    if "ppt/presentation.xml" not in _zip_seguro(contenido, nombre):
        raise ValidationError({CAMPO: f"«{nombre}» no es una presentación de PowerPoint válida."})
    prs = Presentation(BytesIO(contenido))
    partes = []
    for i, diapositiva in enumerate(prs.slides, start=1):
        if i > max_paginas():
            advertencias.append(f"De «{nombre}» solo se leyeron las primeras {max_paginas()} diapositivas.")
            break
        textos = []
        for forma in diapositiva.shapes:
            if forma.has_text_frame and forma.text_frame.text.strip():
                textos.append(forma.text_frame.text)
            if getattr(forma, "has_table", False) and forma.has_table:
                for fila in forma.table.rows:
                    textos.append(" | ".join(c.text for c in fila.cells))
        if diapositiva.has_notes_slide and diapositiva.notes_slide.notes_text_frame.text.strip():
            textos.append("Notas: " + diapositiva.notes_slide.notes_text_frame.text)
        if textos:
            partes.append(f"[Diapositiva {i}]\n" + "\n".join(textos))
    return "\n\n".join(partes)


def _texto_docx(contenido, nombre, advertencias):
    from docx import Document

    if "word/document.xml" not in _zip_seguro(contenido, nombre):
        raise ValidationError({CAMPO: f"«{nombre}» no es un documento de Word válido."})
    doc = Document(BytesIO(contenido))
    partes = [p.text for p in doc.paragraphs if p.text.strip()]
    for tabla in doc.tables:
        for fila in tabla.rows:
            partes.append(" | ".join(c.text for c in fila.cells))
    return "\n".join(partes)


def _pdf(contenido, nombre, advertencias):
    """Devuelve (texto, None) si el PDF tiene texto, o (None, bytes) si es escaneado."""
    import pdfplumber

    try:
        pdf = pdfplumber.open(BytesIO(contenido))
    except Exception:
        raise ValidationError({CAMPO: f"No se pudo leer «{nombre}»."}) from None
    with pdf:
        total = len(pdf.pages)
        if total > max_paginas():
            advertencias.append(f"De «{nombre}» solo se leyeron las primeras {max_paginas()} de {total} páginas.")
        paginas = [p.extract_text() or "" for p in pdf.pages[: max_paginas()]]
    utiles = sum(len(re.sub(r"\W", "", t)) >= MIN_TEXTO_PAGINA for t in paginas)
    if utiles == 0:
        if total > max_paginas():
            raise ValidationError({CAMPO: f"«{nombre}» es un PDF escaneado de más de {max_paginas()} páginas. Envía solo las necesarias."})
        advertencias.append(f"«{nombre}» parece escaneado: la IA lo leerá como imagen (revisa bien el resultado).")
        return None, contenido
    return "\n\n".join(f"[Página {i}]\n{t}" for i, t in enumerate(paginas, start=1) if t.strip()), None


def _texto_plano(contenido, nombre):
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    raise ValidationError({CAMPO: f"No se pudo leer «{nombre}» como texto."})


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def procesar(archivos_subidos):
    """Valida y procesa los archivos del docente. Devuelve un Material (puede estar vacío)."""
    material = Material()
    if not archivos_subidos:
        return material
    if len(archivos_subidos) > max_archivos():
        raise ValidationError({CAMPO: f"Puedes adjuntar hasta {max_archivos()} archivos."})
    if sum(a.size for a in archivos_subidos) > max_mb() * 2 * 1024 * 1024:
        raise ValidationError({CAMPO: f"Los archivos juntos superan los {max_mb() * 2} MB."})

    omitidos = 0
    for archivo in archivos_subidos:
        nombre = archivo.name.rsplit("/", 1)[-1][:120]
        extension = ("." + nombre.rsplit(".", 1)[-1].lower()) if "." in nombre else ""
        if extension not in EXTENSIONES:
            raise ValidationError({CAMPO: f"«{nombre}»: formato no admitido. Usa PDF, PPTX, DOCX, TXT o imágenes JPG/PNG/WEBP."})
        if archivo.size > max_mb() * 1024 * 1024:
            raise ValidationError({CAMPO: f"«{nombre}» supera los {max_mb()} MB."})
        material.nombres.append(nombre)

        if extension in (".jpg", ".jpeg", ".png", ".webp"):
            jpeg = archivos.limpiar_imagen(archivo, max_mb(), CAMPO)  # valida y quita EXIF
            material.adjuntos.append((nombre, "image/jpeg", jpeg))
            continue

        if extension == ".pdf":
            contenido = archivos.validar_pdf(archivo, max_mb(), CAMPO)
            texto, escaneado = _pdf(contenido, nombre, material.advertencias)
            if escaneado is not None:
                material.adjuntos.append((nombre, "application/pdf", escaneado))
                continue
        else:
            archivo.seek(0)
            contenido = archivo.read()
            if extension == ".pptx":
                texto = _texto_pptx(contenido, nombre, material.advertencias)
            elif extension == ".docx":
                texto = _texto_docx(contenido, nombre, material.advertencias)
            else:
                texto = _texto_plano(contenido, nombre)

        texto, n = anonimizar(_normalizar(texto))
        omitidos += n
        if len(texto) < 20:
            material.advertencias.append(f"«{nombre}» no tiene texto suficiente; se ignoró.")
            continue
        material.textos.append((nombre, texto))

    if omitidos:
        material.advertencias.append(
            f"Se ocultaron {omitidos} posibles datos personales (correos, cédulas o teléfonos) del material."
        )

    # Recorte proporcional si el texto total supera el límite.
    total = sum(len(t) for _, t in material.textos)
    if total > max_caracteres():
        proporcion = max_caracteres() / total
        material.textos = [(n, t[: int(len(t) * proporcion)]) for n, t in material.textos]
        material.advertencias.append(
            f"El material es extenso: se usaron unos {max_caracteres():,} caracteres.".replace(",", ".")
        )
    if material.vacio:
        raise ValidationError({CAMPO: "No se pudo obtener contenido útil de los archivos adjuntos."})
    return material


def bloque_para_prompt(material):
    """Texto del material, delimitado, para incluirlo en el prompt."""
    partes = []
    for nombre, texto in material.textos:
        partes.append(f'<material_docente archivo="{nombre}">\n{texto}\n</material_docente>')
    for nombre, mime, _ in material.adjuntos:
        tipo = "PDF escaneado" if mime == "application/pdf" else "imagen"
        partes.append(f'<material_docente archivo="{nombre}">[{tipo} adjunta a esta solicitud]</material_docente>')
    return "\n".join(partes)
