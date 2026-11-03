"""
Archivos de las actividades.

1) Adjuntos del docente (PDF): instrucciones, rúbrica o taller que el estudiante debe hacer.
   - Solo el docente de la actividad; máximo ADJUNTOS_POR_ACTIVIDAD; hasta ADJUNTO_MAX_MB.
   - Los ven el docente, el administrador y los representantes del paralelo.

2) Entregas desde la app (modalidad APP): el representante sube fotos o PDF del trabajo.
   - Solo en actividades publicadas con modalidad «desde la app».
   - Solo el representante del estudiante, y solo para estudiantes activos del paralelo.
   - Máximo ARCHIVOS_POR_ENTREGA por estudiante; hasta ENTREGA_MAX_MB por archivo.
   - Las fotos se re-codifican (sin EXIF/GPS); los PDF se validan por su contenido.
   - Se acepta después del plazo, pero queda marcada como TARDÍA.
   - Cuando el docente ya registró la nota del estudiante, la entrega se cierra (no se
     puede subir ni eliminar).
"""

from datetime import datetime, time

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.academic.models import Estudiante
from apps.grades.models import Calificacion
from apps.security.models import Role

from . import archivos
from .models import Actividad, AdjuntoActividad, ArchivoEntrega


# --------------------------------------------------------------------------- adjuntos
@transaction.atomic
def subir_adjunto(actividad, usuario, archivo):
    actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
    if actividad.asignacion.docente_id != usuario.id:
        raise PermissionDenied("Solo el docente de la actividad puede adjuntar archivos.")
    if actividad.estado == Actividad.Estado.CANCELADA:
        raise ValidationError({"detail": "La actividad está cancelada."})
    if actividad.adjuntos.count() >= settings.ADJUNTOS_POR_ACTIVIDAD:
        raise ValidationError(
            {"detail": f"Cada actividad admite hasta {settings.ADJUNTOS_POR_ACTIVIDAD} PDF."}
        )
    contenido = archivos.validar_pdf(archivo, settings.ADJUNTO_MAX_MB)
    adjunto = AdjuntoActividad(
        actividad=actividad,
        nombre=archivos.nombre_seguro(archivo.name, "pdf"),
        tamano=len(contenido),
        subido_por=usuario,
    )
    adjunto.archivo.save("adjunto.pdf", ContentFile(contenido), save=False)
    adjunto.save()
    return adjunto


def eliminar_adjunto(adjunto, usuario):
    if adjunto.actividad.asignacion.docente_id != usuario.id:
        raise PermissionDenied("Solo el docente de la actividad puede eliminar sus archivos.")
    _borrar(adjunto)


# --------------------------------------------------------------------------- entregas
def limite_entrega(actividad):
    """Momento límite de la entrega (sin hora fijada: hasta el final del día)."""
    hora = actividad.hora_entrega if actividad.tiene_hora else time(23, 59, 59)
    return timezone.make_aware(datetime.combine(actividad.fecha_entrega, hora))


def _calificada(actividad, estudiante_id):
    return Calificacion.objects.filter(actividad=actividad, estudiante_id=estudiante_id).exists()


@transaction.atomic
def subir_entrega(actividad, usuario, estudiante_id, archivo, comentario=""):
    if usuario.role != Role.REPRESENTANTE:
        raise PermissionDenied("Solo el representante puede subir la entrega.")
    actividad = Actividad.objects.select_for_update().select_related("asignacion").get(pk=actividad.pk)
    if actividad.modalidad_entrega != Actividad.ModalidadEntrega.APP:
        raise ValidationError({"detail": "Esta actividad se entrega de forma presencial."})
    if actividad.estado == Actividad.Estado.CANCELADA:
        raise ValidationError({"detail": "La actividad está cancelada."})
    try:
        estudiante_id = int(estudiante_id)
    except (TypeError, ValueError):
        raise ValidationError({"estudiante": "Indica el estudiante."}) from None
    estudiante = Estudiante.objects.filter(
        pk=estudiante_id,
        representante=usuario,
        is_active=True,
        paralelo_id=actividad.asignacion.paralelo_id,
    ).first()
    if estudiante is None:
        raise ValidationError({"estudiante": "El estudiante no es tu representado en este paralelo."})
    if _calificada(actividad, estudiante.id):
        raise ValidationError({"detail": "El docente ya calificó esta actividad; la entrega está cerrada."})
    if actividad.archivos_entrega.filter(estudiante=estudiante).count() >= settings.ARCHIVOS_POR_ENTREGA:
        raise ValidationError(
            {"detail": f"Cada entrega admite hasta {settings.ARCHIVOS_POR_ENTREGA} archivos."}
        )
    comentario = (comentario or "").strip()
    if len(comentario) > 300:
        raise ValidationError({"comentario": "Máximo 300 caracteres."})

    tipo, contenido, extension = archivos.procesar_imagen_o_pdf(archivo, settings.ENTREGA_MAX_MB)
    registro = ArchivoEntrega(
        actividad=actividad,
        estudiante=estudiante,
        tipo=tipo,
        nombre=archivos.nombre_seguro(archivo.name, extension),
        tamano=len(contenido),
        comentario=comentario,
        subido_por=usuario,
    )
    registro.archivo.save(f"entrega.{extension}", ContentFile(contenido), save=False)
    registro.save()
    return registro


def eliminar_archivo_entrega(registro, usuario):
    if registro.subido_por_id != usuario.id:
        raise PermissionDenied("Solo quien subió el archivo puede eliminarlo.")
    if _calificada(registro.actividad, registro.estudiante_id):
        raise ValidationError({"detail": "El docente ya calificó esta actividad; la entrega está cerrada."})
    _borrar(registro)


def _borrar(registro):
    nombre, almacen = registro.archivo.name, registro.archivo.storage
    registro.delete()
    transaction.on_commit(lambda: almacen.delete(nombre))


def entregas_de(actividad, usuario):
    """
    Estado de la entrega por estudiante.
    Docente/administrador: todos los estudiantes activos del paralelo.
    Representante: solo sus estudiantes.
    """
    estudiantes = Estudiante.objects.filter(
        paralelo_id=actividad.asignacion.paralelo_id, is_active=True
    ).order_by("last_name", "first_name")
    if usuario.role == Role.REPRESENTANTE:
        estudiantes = estudiantes.filter(representante=usuario)

    archivos_por_est = {}
    for a in actividad.archivos_entrega.filter(estudiante__in=estudiantes).select_related("subido_por"):
        archivos_por_est.setdefault(a.estudiante_id, []).append(a)
    calificados = set(
        Calificacion.objects.filter(actividad=actividad, estudiante__in=estudiantes).values_list(
            "estudiante_id", flat=True
        )
    )
    limite = limite_entrega(actividad)
    resultado = []
    for e in estudiantes:
        lista = archivos_por_est.get(e.id, [])
        primera = lista[0].created_at if lista else None
        resultado.append(
            {
                "estudiante": e.id,
                "estudiante_nombre": e.full_name,
                "entregada": bool(lista),
                "entregada_en": primera,
                "tardia": bool(primera and primera > limite),
                "calificada": e.id in calificados,
                "archivos": [
                    {
                        "id": a.id,
                        "tipo": a.tipo,
                        "nombre": a.nombre,
                        "tamano": a.tamano,
                        "comentario": a.comentario,
                        "subido_por": a.subido_por_id,
                        "subido_por_nombre": a.subido_por.full_name,
                        "created_at": a.created_at,
                    }
                    for a in lista
                ],
            }
        )
    return {
        "modalidad_entrega": actividad.modalidad_entrega,
        "limite": limite,
        "maximo_archivos": settings.ARCHIVOS_POR_ENTREGA,
        "entregas": resultado,
    }
