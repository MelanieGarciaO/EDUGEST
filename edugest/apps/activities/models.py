from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from . import clock

SIN_HORA = time(0, 0)  # 00:00 = el docente no fijó una hora: la entrega vale todo el día


class Extraccion(models.Model):
    """
    Resultado de procesar con PLN una indicación del docente (la "vista previa").
    No es una actividad: sirve de trazabilidad para comparar lo que propuso el sistema
    con lo que el docente terminó publicando (evaluación de la precisión del PLN).
    """

    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="extracciones_pln"
    )
    paralelo = models.ForeignKey(
        "academic.Paralelo", on_delete=models.PROTECT, related_name="+"
    )
    texto_original = models.TextField("indicación original")
    resultado = models.JSONField("resultado de la extracción", default=dict)
    motor = models.CharField("motor", max_length=20)  # "spacy" o "reglas"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "extracción PLN"
        verbose_name_plural = "extracciones PLN"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Extracción #{self.pk} ({self.motor})"


def _momento_actual(hoy=None, hora=None):
    """(fecha, hora) de referencia. Si solo se pasa la fecha, la hora no influye (cuenta todo el día)."""
    if hoy is None:
        return timezone.localdate(), clock.hora_actual()
    return hoy, hora if hora is not None else SIN_HORA


class ActividadQuerySet(models.QuerySet):
    @staticmethod
    def _vencidas_q(hoy, hora):
        """Vencida: pasó el día de entrega, o es hoy, tiene hora fijada y ya llegó."""
        q = Q(fecha_entrega__lt=hoy)
        if hora != SIN_HORA:
            q |= Q(fecha_entrega=hoy, hora_entrega__lte=hora) & ~Q(hora_entrega=SIN_HORA)
        return q

    def pendientes(self, hoy=None, hora=None):
        hoy, hora = _momento_actual(hoy, hora)
        return self.filter(estado=Actividad.Estado.PUBLICADA).exclude(self._vencidas_q(hoy, hora))

    def finalizadas(self, hoy=None, hora=None):
        hoy, hora = _momento_actual(hoy, hora)
        return self.filter(estado=Actividad.Estado.PUBLICADA).filter(self._vencidas_q(hoy, hora))

    def canceladas(self):
        return self.filter(estado=Actividad.Estado.CANCELADA)


class Actividad(models.Model):
    """
    Tarea publicada por un docente para un paralelo y una asignatura. Se liga a la
    AsignacionDocente (docente + paralelo + asignatura), de modo que solo puede publicarse
    lo que el docente realmente imparte.
    """

    class Estado(models.TextChoices):
        PUBLICADA = "PUBLICADA", "Publicada"
        CANCELADA = "CANCELADA", "Cancelada"

    asignacion = models.ForeignKey(
        "academic.AsignacionDocente", on_delete=models.PROTECT, related_name="actividades"
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="actividades_creadas"
    )
    descripcion = models.TextField("descripción")
    fecha_entrega = models.DateField("fecha de entrega", db_index=True)
    hora_entrega = models.TimeField(
        "hora de entrega",
        default=SIN_HORA,
        help_text="00:00 significa sin hora específica: la entrega vale hasta el final del día.",
    )
    materiales = models.JSONField("materiales", default=list, blank=True)
    tema = models.CharField("tema", max_length=150, blank=True)
    es_evaluacion_refuerzo = models.BooleanField(
        "evaluación de refuerzo",
        default=False,
        help_text=(
            "La nota de esta actividad evalúa los planes de refuerzo completados de los "
            "estudiantes en el tema calificado."
        ),
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PUBLICADA, db_index=True
    )

    texto_original = models.TextField("indicación original", blank=True)
    extraccion = models.OneToOneField(
        Extraccion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="actividad",
    )

    created_at = models.DateTimeField("publicada el", auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelada_en = models.DateTimeField(null=True, blank=True)

    objects = ActividadQuerySet.as_manager()

    class Meta:
        verbose_name = "actividad"
        verbose_name_plural = "actividades"
        ordering = ["fecha_entrega", "hora_entrega", "id"]

    def __str__(self):
        return f"{self.asignacion.asignatura} - {self.fecha_entrega}"

    @property
    def tiene_hora(self):
        return self.hora_entrega != SIN_HORA

    def vencida(self, hoy=None, hora=None):
        """Pasó el día de entrega, o es hoy y la hora fijada ya llegó (sin hora: todo el día)."""
        hoy, hora = _momento_actual(hoy, hora)
        if self.fecha_entrega != hoy:
            return self.fecha_entrega < hoy
        return self.tiene_hora and self.hora_entrega <= hora

    def vigencia(self, hoy=None, hora=None):
        """'cancelada', 'finalizada' (plazo vencido) o 'pendiente'. Se deduce, no se marca."""
        if self.estado == self.Estado.CANCELADA:
            return "cancelada"
        return "finalizada" if self.vencida(hoy, hora) else "pendiente"
