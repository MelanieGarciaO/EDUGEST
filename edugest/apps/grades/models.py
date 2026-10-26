from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from . import scale


class Calificacion(models.Model):
    """
    Nota de un estudiante en una actividad, asociada a un tema del catálogo. Es solo para
    seguimiento y análisis: no reemplaza el sistema oficial de calificaciones.
    """

    actividad = models.ForeignKey(
        "activities.Actividad", on_delete=models.PROTECT, related_name="calificaciones"
    )
    estudiante = models.ForeignKey(
        "academic.Estudiante", on_delete=models.PROTECT, related_name="calificaciones"
    )
    tema = models.ForeignKey(
        "academic.Tema", on_delete=models.PROTECT, related_name="calificaciones"
    )
    valor = models.DecimalField(
        "nota",
        max_digits=4,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("10"))],
    )
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="calificaciones_registradas"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "calificación"
        verbose_name_plural = "calificaciones"
        ordering = ["-actividad__fecha_entrega", "estudiante__last_name", "estudiante__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["actividad", "estudiante"], name="unique_calificacion_por_actividad"
            ),
            models.CheckConstraint(
                condition=models.Q(valor__gte=0, valor__lte=10), name="calificacion_entre_0_y_10"
            ),
        ]

    def __str__(self):
        return f"{self.estudiante} - {self.valor}"

    @property
    def nivel(self):
        return scale.nivel_cualitativo(self.valor)


class CalificacionHistorial(models.Model):
    """Registro de cada corrección de una nota (las notas no se borran)."""

    calificacion = models.ForeignKey(
        Calificacion, on_delete=models.PROTECT, related_name="historial"
    )
    valor_anterior = models.DecimalField(max_digits=4, decimal_places=2)
    valor_nuevo = models.DecimalField(max_digits=4, decimal_places=2)
    tema_anterior = models.ForeignKey(
        "academic.Tema", on_delete=models.PROTECT, related_name="+"
    )
    tema_nuevo = models.ForeignKey(
        "academic.Tema", on_delete=models.PROTECT, related_name="+"
    )
    modificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "historial de calificación"
        verbose_name_plural = "historial de calificaciones"
        ordering = ["-created_at", "-id"]


class Dificultad(models.Model):
    """
    Dificultad académica de un estudiante en un tema. Se crea y se actualiza sola cada vez
    que se guardan notas (ver services.recalcular_dificultad). El módulo de refuerzo parte
    de estos registros.
    """

    class Nivel(models.TextChoices):
        MODERADA = scale.MODERADA, "Moderada"
        ALTA = scale.ALTA, "Alta"

    class Estado(models.TextChoices):
        DETECTADA = "DETECTADA", "Detectada"
        SUPERADA = "SUPERADA", "Superada"

    estudiante = models.ForeignKey(
        "academic.Estudiante", on_delete=models.PROTECT, related_name="dificultades"
    )
    tema = models.ForeignKey(
        "academic.Tema", on_delete=models.PROTECT, related_name="dificultades"
    )
    promedio = models.DecimalField(max_digits=4, decimal_places=2)
    num_calificaciones = models.PositiveIntegerField()
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.DETECTADA, db_index=True
    )
    detectada_en = models.DateTimeField(auto_now_add=True)
    superada_en = models.DateTimeField(null=True, blank=True)
    # Cuántas veces se detectó la dificultad en este tema. Sube cuando una dificultad ya
    # SUPERADA vuelve a DETECTADA (el estudiante recae en la misma destreza).
    veces_detectada = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def reincidente(self):
        """True si el estudiante ya había superado esta dificultad y volvió a presentarla."""
        return self.veces_detectada > 1

    class Meta:
        verbose_name = "dificultad"
        verbose_name_plural = "dificultades"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["estudiante", "tema"], name="unique_dificultad_por_estudiante_y_tema"
            )
        ]

    def __str__(self):
        return f"{self.estudiante} - {self.tema} ({self.get_estado_display()})"
