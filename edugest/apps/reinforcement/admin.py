from django.contrib import admin
from rest_framework.exceptions import ValidationError

from apps.admin_acciones import AccionesActivoMixin, informar, primer_error

from . import services
from .models import ActividadRefuerzo, PlanRefuerzo, RecursoRefuerzo, TemaPlan


@admin.register(RecursoRefuerzo)
class RecursoRefuerzoAdmin(AccionesActivoMixin, admin.ModelAdmin):
    list_display = ("titulo", "tema", "nivel", "estrategia", "is_active", "creado_por")
    list_filter = ("nivel", "estrategia", "is_active", "tema__asignatura", "tema__grado")
    search_fields = ("titulo", "instrucciones")
    raw_id_fields = ("tema", "creado_por")


class ActividadInline(admin.TabularInline):
    model = ActividadRefuerzo
    extra = 0
    can_delete = False
    readonly_fields = ("titulo", "origen", "nivel", "estado", "cumplida_en", "cumplida_por")

    def has_add_permission(self, request, obj=None):
        return False


class TemaPlanInline(admin.TabularInline):
    model = TemaPlan
    extra = 0
    can_delete = False
    readonly_fields = ("tema", "orden", "origen", "motivo", "objetivo", "promedio_inicial", "nivel_dificultad", "sin_recursos")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PlanRefuerzo)
class PlanRefuerzoAdmin(admin.ModelAdmin):
    """
    Solo lectura: los planes se gestionan por la API, con sus reglas y eventos. La única
    acción es «Cancelar», con la misma lógica de la app (avisa a la familia). Aprobar es
    decisión del docente; «Completado» y la evaluación los marca el sistema.
    """

    actions = ("cancelar_planes",)

    list_display = ("id", "estudiante", "asignatura", "nivel", "estado", "docente", "created_at")
    list_filter = ("estado", "nivel", "asignatura")
    search_fields = ("estudiante__first_name", "estudiante__last_name")
    inlines = [TemaPlanInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Cancelar planes seleccionados (en propuesta o aprobados)")
    def cancelar_planes(self, request, queryset):
        hechos, omitidos = 0, []
        for plan in queryset:
            try:
                services.cancelar_plan(plan, request.user)
                hechos += 1
            except ValidationError as exc:
                omitidos.append(f"{plan}: {primer_error(exc)}")
        informar(self, request, hechos, omitidos, "cancelados")
