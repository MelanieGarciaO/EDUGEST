from django.contrib import admin
from django.db import transaction
from django.utils import timezone

from apps.admin_acciones import informar

from .models import Actividad, Extraccion
from .signals import actividad_cancelada


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("id", "asignacion", "fecha_entrega", "estado", "es_evaluacion_refuerzo", "creada_por")
    list_filter = ("estado", "es_evaluacion_refuerzo", "asignacion__paralelo", "asignacion__asignatura")
    search_fields = ("descripcion", "tema")
    date_hierarchy = "fecha_entrega"
    raw_id_fields = ("asignacion", "creada_por", "extraccion")
    # En una evaluación de refuerzo: a quién va dirigida (los que completaron su plan).
    filter_horizontal = ("destinatarios",)
    readonly_fields = ("texto_original", "created_at", "updated_at", "cancelada_en")
    actions = ("cancelar_actividades", "publicar_actividades")

    @admin.action(description="Cancelar actividades seleccionadas")
    def cancelar_actividades(self, request, queryset):
        """Igual que «Cancelar actividad» en la app: marca la fecha y avisa a las familias."""
        pendientes = list(queryset.exclude(estado=Actividad.Estado.CANCELADA))
        ahora = timezone.now()
        for actividad in pendientes:
            actividad.estado = Actividad.Estado.CANCELADA
            actividad.cancelada_en = ahora
            actividad.save(update_fields=["estado", "cancelada_en", "updated_at"])
            transaction.on_commit(
                lambda a=actividad: actividad_cancelada.send(sender=Actividad, actividad=a)
            )
        omitidas = [f"{a}: ya estaba cancelada." for a in queryset.filter(estado=Actividad.Estado.CANCELADA)]
        informar(self, request, len(pendientes), omitidas, "canceladas")

    @admin.action(description="Volver a publicar actividades seleccionadas")
    def publicar_actividades(self, request, queryset):
        """Revierte una cancelación hecha por error (no envía avisos)."""
        omitidas = [f"{a}: ya estaba publicada." for a in queryset.filter(estado=Actividad.Estado.PUBLICADA)]
        hechas = queryset.exclude(estado=Actividad.Estado.PUBLICADA).update(
            estado=Actividad.Estado.PUBLICADA, cancelada_en=None, updated_at=timezone.now()
        )
        informar(self, request, hechas, omitidas, "publicadas de nuevo")


@admin.register(Extraccion)
class ExtraccionAdmin(admin.ModelAdmin):
    """Solo lectura: es el registro de lo que propuso el PLN, útil para evaluar su precisión."""

    list_display = ("id", "docente", "paralelo", "motor", "created_at")
    list_filter = ("motor",)
    readonly_fields = ("docente", "paralelo", "texto_original", "resultado", "motor", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
