from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.security.models import Role


class Grado(models.Model):
    """Grado de Educación General Básica (1.º a 10.º)."""

    nombre = models.CharField("nombre", max_length=50, unique=True)
    orden = models.PositiveSmallIntegerField(
        "orden",
        unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Posición del grado dentro de EGB (1 a 10).",
    )

    class Meta:
        verbose_name = "grado"
        verbose_name_plural = "grados"
        ordering = ["orden"]

    def __str__(self):
        return self.nombre


class Paralelo(models.Model):
    """Paralelo de un grado (A, B, C...). Equivale al 'grupo' que ve el docente."""

    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name="paralelos")
    nombre = models.CharField("nombre", max_length=10)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "paralelo"
        verbose_name_plural = "paralelos"
        ordering = ["grado__orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["grado", "nombre"], name="unique_paralelo_por_grado"
            )
        ]

    def save(self, *args, **kwargs):
        self.nombre = self.nombre.strip().upper()
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return f"{self.grado.nombre} {self.nombre}"

    def __str__(self):
        return self.nombre_completo


class Asignatura(models.Model):
    nombre = models.CharField("nombre", max_length=100, unique=True)
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "asignatura"
        verbose_name_plural = "asignaturas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Tema(models.Model):
    """
    Catálogo curricular: temas de una asignatura en un grado. Un tema puede tener
    subtemas (un solo nivel de profundidad). Lo carga el administrador; lo usan las
    calificaciones (para analizar el desempeño por tema) y el banco de refuerzo.
    """

    grado = models.ForeignKey(Grado, on_delete=models.PROTECT, related_name="temas")
    asignatura = models.ForeignKey(Asignatura, on_delete=models.PROTECT, related_name="temas")
    padre = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subtemas",
        help_text="Si se indica, este registro es un subtema del tema padre.",
    )
    nombre = models.CharField("nombre", max_length=150)
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "tema"
        verbose_name_plural = "temas"
        ordering = ["grado__orden", "asignatura__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["grado", "asignatura", "nombre"],
                condition=models.Q(padre__isnull=True),
                name="unique_tema_por_grado_y_asignatura",
            ),
            models.UniqueConstraint(
                fields=["padre", "nombre"],
                condition=models.Q(padre__isnull=False),
                name="unique_subtema_por_tema",
            ),
        ]

    @property
    def es_subtema(self):
        return self.padre_id is not None

    def __str__(self):
        if self.padre_id:
            return f"{self.padre.nombre} > {self.nombre}"
        return self.nombre


class Estudiante(models.Model):
    """
    Estudiante (menor de edad). NO es un usuario del sistema: existe solo como
    registro asociado a un paralelo y a un representante. Se guardan únicamente los
    datos indispensables.
    """

    first_name = models.CharField("nombres", max_length=150)
    last_name = models.CharField("apellidos", max_length=150)
    paralelo = models.ForeignKey(
        Paralelo, on_delete=models.PROTECT, related_name="estudiantes"
    )
    representante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="estudiantes_representados",
        limit_choices_to={"role": Role.REPRESENTANTE},
    )
    is_active = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "estudiante"
        verbose_name_plural = "estudiantes"
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name


class AsignacionDocente(models.Model):
    """
    Un docente imparte una asignatura en un paralelo. Define qué grupos ve y gestiona
    cada docente. Por paralelo y asignatura hay un solo docente; para cambiarlo se edita
    la asignación existente.
    """

    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones",
        limit_choices_to={"role": Role.DOCENTE},
    )
    paralelo = models.ForeignKey(
        Paralelo, on_delete=models.PROTECT, related_name="asignaciones"
    )
    asignatura = models.ForeignKey(
        Asignatura, on_delete=models.PROTECT, related_name="asignaciones"
    )
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "asignación docente"
        verbose_name_plural = "asignaciones docentes"
        ordering = ["paralelo__grado__orden", "paralelo__nombre", "asignatura__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["paralelo", "asignatura"],
                name="unique_docente_por_paralelo_asignatura",
            )
        ]

    def __str__(self):
        return f"{self.docente.full_name} - {self.asignatura} - {self.paralelo}"