from django.contrib import admin

from .models import Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo, Tema


@admin.register(Grado)
class GradoAdmin(admin.ModelAdmin):
    list_display = ("orden", "nombre")
    ordering = ("orden",)


@admin.register(Paralelo)
class ParaleloAdmin(admin.ModelAdmin):
    list_display = ("__str__", "grado", "is_active")
    list_filter = ("grado", "is_active")


@admin.register(Asignatura)
class AsignaturaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "is_active")
    list_filter = ("is_active",)
    search_fields = ("nombre",)


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ("full_name", "paralelo", "representante", "is_active")
    list_filter = ("paralelo__grado", "paralelo", "is_active")
    search_fields = ("first_name", "last_name")
    autocomplete_fields = ()
    raw_id_fields = ("representante",)


@admin.register(AsignacionDocente)
class AsignacionDocenteAdmin(admin.ModelAdmin):
    list_display = ("docente", "asignatura", "paralelo", "is_active")
    list_filter = ("paralelo__grado", "paralelo", "asignatura", "is_active")
    raw_id_fields = ("docente",)


@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "grado", "asignatura", "is_active")
    list_filter = ("grado", "asignatura", "is_active")
    search_fields = ("nombre",)
    raw_id_fields = ("padre",)
