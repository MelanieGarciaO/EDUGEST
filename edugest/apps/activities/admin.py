from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from .models import Actividad, Extraccion
from .signals import actividad_cancelada


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("id", "asignacion", "fecha_entrega", "estado", "creada_por")
    list_filter = ("estado", "asignacion__paralelo", "asignacion__asignatura")
    search_fields = ("descripcion", "tema")
    date_hierarchy = "fecha_entrega"
    raw_id_fields = ("asignacion", "creada_por", "extraccion")
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
        self._informar(request, len(pendientes), queryset.count(), "cancelada", "canceladas", "ya estaban canceladas")

    @admin.action(description="Volver a publicar actividades seleccionadas")
    def publicar_actividades(self, request, queryset):
        """Revierte una cancelación hecha por error (no envía avisos)."""
        n = queryset.exclude(estado=Actividad.Estado.PUBLICADA).update(
            estado=Actividad.Estado.PUBLICADA, cancelada_en=None, updated_at=timezone.now()
        )
        self._informar(request, n, queryset.count(), "publicada", "publicadas", "ya estaban publicadas")

    def _informar(self, request, cambiadas, total, singular, plural, sin_cambio):
        if cambiadas:
            self.message_user(
                request, f"{cambiadas} actividad{'es' if cambiadas != 1 else ''} {plural if cambiadas != 1 else singular}.",
                messages.SUCCESS,
            )
        if total - cambiadas:
            self.message_user(request, f"{total - cambiadas} {sin_cambio}: no se modificaron.", messages.INFO)


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
