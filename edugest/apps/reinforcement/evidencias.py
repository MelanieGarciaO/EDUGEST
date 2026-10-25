"""
Evidencias fotográficas de las actividades de refuerzo (mejora 14).

Protección de datos (LOPDP; los estudiantes son menores de edad):
- Solo el representante del estudiante puede subir fotos, y solo de un plan publicado.
- Cada imagen se valida con Pillow y se RE-CODIFICA a JPEG: se eliminan los metadatos
  EXIF (incluida la ubicación GPS) y se reduce a 1600 px como máximo.
- El almacenamiento es privado (bucket de Supabase sin acceso público). Las fotos se
  entregan solo a través de la API, al representante y al docente del plan.
- Se recomienda en pantalla fotografiar el trabajo, no el rostro del estudiante.
"""

from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.security.models import Role

from .models import ActividadRefuerzo, EvidenciaActividad, PlanRefuerzo

FORMATOS = {"JPEG", "PNG", "WEBP"}
LADO_MAXIMO = 1600
CALIDAD = 82
Image.MAX_IMAGE_PIXELS = 40_000_000  # evita «bombas» de descompresión


def _limpiar_imagen(archivo):
    """Valida la imagen y devuelve bytes JPEG sin metadatos."""
    maximo = settings.EVIDENCIA_MAX_MB * 1024 * 1024
    if archivo.size > maximo:
        raise ValidationError({"archivo": f"La foto supera los {settings.EVIDENCIA_MAX_MB} MB."})
    try:
        with Image.open(archivo) as prueba:
            formato = prueba.format
            prueba.verify()
        archivo.seek(0)
        with Image.open(archivo) as img:
            img.load()
            if formato not in FORMATOS:
                raise ValidationError({"archivo": "Formato no admitido. Usa JPG, PNG o WEBP."})
            img = ImageOps.exif_transpose(img)  # respeta la orientación antes de quitar EXIF
            img = img.convert("RGB")
            img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            salida = BytesIO()
            img.save(salida, format="JPEG", quality=CALIDAD, optimize=True)  # sin exif=
            return salida.getvalue()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ValidationError({"archivo": "El archivo no es una imagen válida."}) from None


@transaction.atomic
def subir(actividad, usuario, archivo, comentario=""):
    if usuario.role != Role.REPRESENTANTE:
        raise PermissionDenied("Solo el representante puede subir evidencias.")
    if not archivo:
        raise ValidationError({"archivo": "Adjunta una foto."})
    actividad = ActividadRefuerzo.objects.select_for_update().select_related("tema_plan__plan").get(pk=actividad.pk)
    plan = actividad.tema_plan.plan
    if plan.estado not in (PlanRefuerzo.Estado.APROBADA, PlanRefuerzo.Estado.COMPLETADA):
        raise ValidationError({"detail": "Solo se pueden subir evidencias de un plan publicado."})
    if actividad.evidencias.count() >= settings.EVIDENCIAS_POR_ACTIVIDAD:
        raise ValidationError(
            {"detail": f"Cada actividad admite hasta {settings.EVIDENCIAS_POR_ACTIVIDAD} fotos."}
        )
    comentario = (comentario or "").strip()
    if len(comentario) > 300:
        raise ValidationError({"comentario": "Máximo 300 caracteres."})

    contenido = _limpiar_imagen(archivo)
    evidencia = EvidenciaActividad(
        actividad=actividad, comentario=comentario, tamano=len(contenido), subida_por=usuario
    )
    evidencia.archivo.save("evidencia.jpg", ContentFile(contenido), save=False)
    evidencia.save()
    return evidencia


def eliminar(evidencia, usuario):
    if evidencia.subida_por_id != usuario.id:
        raise PermissionDenied("Solo quien subió la foto puede eliminarla.")
    if evidencia.actividad.tema_plan.plan.estado != PlanRefuerzo.Estado.APROBADA:
        raise ValidationError({"detail": "El plan ya no está en curso; la evidencia se conserva."})
    nombre, almacen = evidencia.archivo.name, evidencia.archivo.storage
    evidencia.delete()
    transaction.on_commit(lambda: almacen.delete(nombre))
