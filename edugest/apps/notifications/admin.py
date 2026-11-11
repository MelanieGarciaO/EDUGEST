from django.contrib import admin

from .models import Notificacion, PreferenciaNotificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "categoria", "titulo", "estado_correo", "leida", "created_at")
    list_filter = ("categoria", "estado_correo", "leida")
    search_fields = ("usuario__email", "titulo")
    readonly_fields = [f.name for f in Notificacion._meta.fields]


@admin.register(PreferenciaNotificacion)
class PreferenciaNotificacionAdmin(admin.ModelAdmin):
    list_display = ("usuario", "actividades", "calificaciones", "refuerzo", "recordatorios")
