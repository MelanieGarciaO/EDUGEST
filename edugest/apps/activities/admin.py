from django.contrib import admin

from .models import Actividad, Extraccion


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ("id", "asignacion", "fecha_entrega", "estado", "creada_por")
    list_filter = ("estado", "asignacion__paralelo", "asignacion__asignatura")
    search_fields = ("descripcion", "tema")
    date_hierarchy = "fecha_entrega"
    raw_id_fields = ("asignacion", "creada_por", "extraccion")
    readonly_fields = ("texto_original", "created_at", "updated_at", "cancelada_en")


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
