"""
Evidencias de las actividades de refuerzo (mejora 14), en varias formas para que el
estudiante demuestre lo aprendido como pueda (DUA · acción y expresión):
- FOTO del trabajo, AUDIO con su explicación o TEXTO con lo que hizo o aprendió.

Protección de datos (LOPDP; los estudiantes son menores de edad):
- Solo el representante del estudiante puede subir fotos, y solo de un plan publicado.
- Cada imagen se valida con Pillow y se RE-CODIFICA a JPEG: se eliminan los metadatos
  EXIF (incluida la ubicación GPS) y se reduce a 1600 px como máximo.
- El almacenamiento es privado (bucket de Supabase sin acceso público). Las fotos se
  entregan solo a través de la API, al representante y al docente del plan.
- Se recomienda en pantalla fotografiar el trabajo, no el rostro del estudiante.
- Los audios se validan por su CONTENIDO (no por el nombre): solo formatos de audio
  conocidos, con tamaño máximo. Se recomienda no decir nombres completos ni datos personales.
- Cada actividad admite hasta EVIDENCIAS_POR_ACTIVIDAD evidencias en total (de cualquier tipo).
"""

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.activities import archivos
from apps.security.models import Role

from .models import ActividadRefuerzo, EvidenciaActividad, PlanRefuerzo


Tipo = EvidenciaActividad.Tipo
TEXTO_MIN, TEXTO_MAX = 10, 1000


def _limpiar_imagen(archivo):
    """Valida la imagen y devuelve bytes JPEG sin metadatos (ver activities/archivos.py)."""
    return archivos.limpiar_imagen(archivo, settings.EVIDENCIA_MAX_MB)


def tipo_audio(cabecera):
    """(content_type, extensión) según los primeros bytes del archivo, o None si no es audio."""
    if cabecera.startswith(b"OggS"):
        return "audio/ogg", "ogg"
    if cabecera.startswith(b"\x1aE\xdf\xa3"):  # WebM (lo que graban Chrome y Firefox)
        return "audio/webm", "webm"
    if cabecera[4:8] == b"ftyp":  # MP4/M4A (lo que graban Safari y los iPhone)
        return "audio/mp4", "m4a"
    if cabecera.startswith(b"RIFF") and cabecera[8:12] == b"WAVE":
        return "audio/wav", "wav"
    if cabecera.startswith(b"ID3") or (len(cabecera) > 1 and cabecera[0] == 0xFF and cabecera[1] & 0xE0 == 0xE0):
        if len(cabecera) > 1 and cabecera[1] & 0x06 == 0:  # capa 0: AAC (ADTS)
            return "audio/aac", "aac"
        return "audio/mpeg", "mp3"
    return None


def _validar_audio(archivo):
    maximo = settings.EVIDENCIA_AUDIO_MAX_MB
    if archivo.size > maximo * 1024 * 1024:
        raise ValidationError({"archivo": f"El audio supera {maximo} MB. Graba un mensaje más corto."})
    archivo.seek(0)
    contenido = archivo.read()
    tipo = tipo_audio(contenido[:16])
    if tipo is None or len(contenido) < 512:
        raise ValidationError({"archivo": "El archivo no es un audio válido. Usa MP3, M4A, OGG, WEBM o WAV."})
    return contenido, *tipo


def _limpiar_texto(texto):
    texto = "\n".join(" ".join(linea.split()) for linea in (texto or "").strip().splitlines()).strip()
    if len(texto) < TEXTO_MIN:
        raise ValidationError({"texto": f"Escribe al menos {TEXTO_MIN} caracteres."})
    if len(texto) > TEXTO_MAX:
        raise ValidationError({"texto": f"Máximo {TEXTO_MAX} caracteres."})
    return texto


@transaction.atomic
def subir(actividad, usuario, archivo, comentario="", tipo=Tipo.FOTO, texto=""):
    if usuario.role != Role.REPRESENTANTE:
        raise PermissionDenied("Solo el representante puede subir evidencias.")
    tipo = (tipo or Tipo.FOTO).upper()
    if tipo not in Tipo.values:
        raise ValidationError({"tipo": "Tipo de evidencia no válido: usa foto, audio o texto."})
    if tipo == Tipo.FOTO and not archivo:
        raise ValidationError({"archivo": "Adjunta una foto."})
    if tipo == Tipo.AUDIO and not archivo:
        raise ValidationError({"archivo": "Graba o adjunta un audio."})
    actividad = ActividadRefuerzo.objects.select_for_update().select_related("tema_plan__plan").get(pk=actividad.pk)
    plan = actividad.tema_plan.plan
    if plan.estado not in (PlanRefuerzo.Estado.APROBADA, PlanRefuerzo.Estado.COMPLETADA):
        raise ValidationError({"detail": "Solo se pueden subir evidencias de un plan publicado."})
    if actividad.evidencias.count() >= settings.EVIDENCIAS_POR_ACTIVIDAD:
        raise ValidationError(
            {"detail": f"Cada actividad admite hasta {settings.EVIDENCIAS_POR_ACTIVIDAD} evidencias."}
        )
    comentario = (comentario or "").strip()
    if len(comentario) > 300:
        raise ValidationError({"comentario": "Máximo 300 caracteres."})

    evidencia = EvidenciaActividad(actividad=actividad, tipo=tipo, comentario=comentario, subida_por=usuario)
    if tipo == Tipo.TEXTO:
        evidencia.texto = _limpiar_texto(texto)
        evidencia.tipo_contenido = ""
        evidencia.save()
        return evidencia

    if tipo == Tipo.FOTO:
        contenido, content_type, extension = _limpiar_imagen(archivo), "image/jpeg", "jpg"
    else:
        contenido, content_type, extension = _validar_audio(archivo)
    evidencia.tamano, evidencia.tipo_contenido = len(contenido), content_type
    evidencia.archivo.save(f"evidencia.{extension}", ContentFile(contenido), save=False)
    evidencia.save()
    return evidencia


def eliminar(evidencia, usuario):
    if evidencia.subida_por_id != usuario.id:
        raise PermissionDenied("Solo quien subió la evidencia puede eliminarla.")
    if evidencia.actividad.tema_plan.plan.estado != PlanRefuerzo.Estado.APROBADA:
        raise ValidationError({"detail": "El plan ya no está en curso; la evidencia se conserva."})
    nombre, almacen = evidencia.archivo.name, evidencia.archivo.storage
    evidencia.delete()
    if nombre:  # las de texto no tienen archivo
        transaction.on_commit(lambda: almacen.delete(nombre))