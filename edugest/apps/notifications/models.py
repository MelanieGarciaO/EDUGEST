"""
Notificaciones de EduGest: registro dentro de la app (campana) y envío por correo (Resend).

- Notificacion: cada aviso que recibe un usuario. Guarda además el estado del correo para
  poder auditar los envíos (enviado, omitido por preferencia, error).
- PreferenciaNotificacion: qué categorías quiere recibir por correo cada usuario. Los avisos
  de SEGURIDAD (cuenta, contraseñas, códigos) siempre se envían y no se pueden desactivar.
"""

from django.conf import settings
from django.db import models


class Categoria(models.TextChoices):
    SEGURIDAD = "SEGURIDAD", "Cuenta y seguridad"
    ACTIVIDADES = "ACTIVIDADES", "Actividades"
    CALIFICACIONES = "CALIFICACIONES", "Calificaciones"
    REFUERZO = "REFUERZO", "Planes de refuerzo"
    RECORDATORIOS = "RECORDATORIOS", "Recordatorios de entrega"


# Categorías que el usuario puede activar o desactivar para el correo.
CONFIGURABLES = [c for c in Categoria.values if c != Categoria.SEGURIDAD]


class Notificacion(models.Model):
    class EstadoCorreo(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADO = "ENVIADO", "Enviado"
        OMITIDO = "OMITIDO", "No enviado (preferencia del usuario)"
        ERROR = "ERROR", "Error al enviar"
        SIN_CORREO = "SIN_CORREO", "Solo en la app"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    categoria = models.CharField(max_length=20, choices=Categoria.choices, db_index=True)
    tipo = models.CharField("tipo de evento", max_length=40)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(max_length=1000)
    enlace = models.CharField("ruta en la app", max_length=300, blank=True)
    leida = models.BooleanField(default=False, db_index=True)
    leida_en = models.DateTimeField(null=True, blank=True)
    estado_correo = models.CharField(max_length=12, choices=EstadoCorreo.choices, default=EstadoCorreo.PENDIENTE)
    error_correo = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"
        indexes = [models.Index(fields=["usuario", "leida", "-created_at"])]

    def __str__(self):
        return f"{self.usuario} · {self.titulo}"


class PreferenciaNotificacion(models.Model):
    """Una fila por usuario; se crea con todo activado la primera vez que se consulta."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferencia_notificaciones"
    )
    actividades = models.BooleanField("correo de actividades", default=True)
    calificaciones = models.BooleanField("correo de calificaciones", default=True)
    refuerzo = models.BooleanField("correo de planes de refuerzo", default=True)
    recordatorios = models.BooleanField("correo de recordatorios", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "preferencia de notificaciones"
        verbose_name_plural = "preferencias de notificaciones"

    def acepta_correo(self, categoria):
        if categoria == Categoria.SEGURIDAD:
            return True
        return getattr(self, categoria.lower(), True)
