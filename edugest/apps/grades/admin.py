from django.contrib import admin

from .models import Calificacion, CalificacionHistorial, Dificultad


class SoloLectura(admin.ModelAdmin):
    """Las notas, su historial y las dificultades se gestionan por la API, no a mano."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class HistorialInline(admin.TabularInline):
    model = CalificacionHistorial
    extra = 0
    can_delete = False
    readonly_fields = (
        "valor_anterior", "valor_nuevo", "tema_anterior", "tema_nuevo", "modificado_por", "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Calificacion)
class CalificacionAdmin(SoloLectura):
    list_display = ("estudiante", "actividad", "tema", "valor", "registrada_por", "updated_at")
    list_filter = ("tema__asignatura", "tema__grado")
    search_fields = ("estudiante__first_name", "estudiante__last_name")
    inlines = [HistorialInline]


@admin.register(Dificultad)
class DificultadAdmin(SoloLectura):
    list_display = ("estudiante", "tema", "promedio", "nivel", "estado", "updated_at")
    list_filter = ("estado", "nivel", "tema__asignatura")
    search_fields = ("estudiante__first_name", "estudiante__last_name")
