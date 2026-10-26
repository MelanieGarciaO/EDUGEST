import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class NivelActividad(models.TextChoices):
    BASICO = "BASICO", "Básico"
    INTERMEDIO = "INTERMEDIO", "Intermedio"
    AVANZADO = "AVANZADO", "Avanzado"


class EstrategiaRefuerzo(models.TextChoices):
    """Tipos de estrategia de refuerzo académico que contempla la normativa (LOEI)."""

    INDIVIDUAL = "INDIVIDUAL", "Trabajo individualizado"
    GRUPAL = "GRUPAL", "Trabajo grupal"
    ENTRE_IGUALES = "ENTRE_IGUALES", "Ayuda entre iguales"
    TECNOLOGIA = "TECNOLOGIA", "Uso de tecnología"
    COOPERATIVO = "COOPERATIVO", "Aprendizaje cooperativo"
    TAREA_CASA = "TAREA_CASA", "Tareas para la casa"


class RecursoRefuerzo(models.Model):
    """
    Actividad del banco de recursos. Se clasifica por tema (o subtema) y nivel; el grado
    y la asignatura se obtienen del tema. Lo cargan los docentes (en lo que imparten) y
    el administrador. No se borra: se desactiva.
    """

    tema = models.ForeignKey(
        "academic.Tema", on_delete=models.PROTECT, related_name="recursos_refuerzo"
    )
    nivel = models.CharField(max_length=10, choices=NivelActividad.choices, db_index=True)
    estrategia = models.CharField(
        "estrategia",
        max_length=15,
        choices=EstrategiaRefuerzo.choices,
        default=EstrategiaRefuerzo.INDIVIDUAL,
    )
    titulo = models.CharField("título", max_length=200)
    instrucciones = models.TextField("instrucciones")
    duracion_minutos = models.PositiveSmallIntegerField(
        "duración estimada (min)",
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(240)],
    )
    is_active = models.BooleanField("activo", default=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="recursos_refuerzo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "recurso de refuerzo"
        verbose_name_plural = "recursos de refuerzo"
        ordering = ["tema__grado__orden", "tema__asignatura__nombre", "tema__nombre", "nivel", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tema", "titulo"], name="unique_recurso_por_tema_y_titulo")
        ]

    def __str__(self):
        return f"{self.titulo} ({self.get_nivel_display()})"


class PlanRefuerzo(models.Model):
    """Propuesta de refuerzo para un estudiante en una asignatura (varios temas)."""

    class Nivel(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        ALTO = "ALTO", "Alto"

    class Estado(models.TextChoices):
        PROPUESTA = "PROPUESTA", "Propuesta"
        APROBADA = "APROBADA", "Aprobada"
        COMPLETADA = "COMPLETADA", "Completada"
        CANCELADA = "CANCELADA", "Cancelada"

    VIGENTES = ("PROPUESTA", "APROBADA")

    estudiante = models.ForeignKey(
        "academic.Estudiante", on_delete=models.PROTECT, related_name="planes_refuerzo"
    )
    asignatura = models.ForeignKey(
        "academic.Asignatura", on_delete=models.PROTECT, related_name="+"
    )
    docente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="planes_refuerzo"
    )
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PROPUESTA, db_index=True
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)
    completado_en = models.DateTimeField(null=True, blank=True)
    cancelado_en = models.DateTimeField(null=True, blank=True)
    # Acuse de recibo: el representante confirma que revisó el plan con el estudiante.
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plan de refuerzo"
        verbose_name_plural = "planes de refuerzo"
        ordering = ["-created_at", "-id"]
        constraints = [
            # Un solo plan vigente (propuesta o aprobado) por estudiante y asignatura.
            models.UniqueConstraint(
                fields=["estudiante", "asignatura"],
                condition=models.Q(estado__in=["PROPUESTA", "APROBADA"]),
                name="unique_plan_vigente_por_estudiante_y_asignatura",
            )
        ]

    def __str__(self):
        return f"Plan #{self.pk} - {self.estudiante} - {self.asignatura}"


class TemaPlan(models.Model):
    """Un tema prioritario dentro de un plan, con su objetivo y sus actividades."""

    plan = models.ForeignKey(PlanRefuerzo, on_delete=models.CASCADE, related_name="temas")
    tema = models.ForeignKey("academic.Tema", on_delete=models.PROTECT, related_name="+")
    class Origen(models.TextChoices):
        DIFICULTAD = "DIFICULTAD", "Dificultad detectada"
        MANUAL = "MANUAL", "Refuerzo solicitado por el docente"

    # Es nula cuando el docente pide reforzar un tema sin dificultad detectada (origen MANUAL).
    dificultad = models.ForeignKey(
        "grades.Dificultad", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    origen = models.CharField(max_length=10, choices=Origen.choices, default=Origen.DIFICULTAD)
    motivo = models.CharField(
        max_length=300,
        blank=True,
        help_text="Por qué el docente pidió reforzar este tema (por ejemplo, una destreza concreta).",
    )
    orden = models.PositiveSmallIntegerField()
    objetivo = models.TextField()
    # Nulo si el estudiante aún no tiene notas en el tema (solo posible en refuerzo manual).
    promedio_inicial = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    nivel_dificultad = models.CharField(max_length=10)
    sin_recursos = models.BooleanField(
        default=False, help_text="El banco no tenía actividades para este tema al generar el plan."
    )

    # --- Evaluación de refuerzo (se llena sola al calificar una actividad marcada como
    # evaluación de refuerzo, después de completar el plan). Nulo = aún no evaluado.
    evaluacion = models.ForeignKey(
        "grades.Calificacion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Nota de la evaluación de refuerzo que cierra este tema del plan.",
    )
    promedio_final = models.DecimalField(
        "promedio del tema tras la evaluación", max_digits=4, decimal_places=2, null=True, blank=True
    )
    superado = models.BooleanField(
        null=True, blank=True, help_text="Resultado de la evaluación. Nulo mientras no se evalúa."
    )
    evaluado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "tema del plan"
        verbose_name_plural = "temas del plan"
        ordering = ["orden", "id"]
        constraints = [
            models.UniqueConstraint(fields=["plan", "tema"], name="unique_tema_por_plan")
        ]

    def __str__(self):
        return f"{self.tema} (plan #{self.plan_id})"


class ActividadRefuerzo(models.Model):
    """
    Actividad asignada dentro de un plan. Copia (no enlaza) el contenido del recurso del
    banco, para que editar el banco después no altere un plan ya aprobado.
    """

    class Origen(models.TextChoices):
        BANCO = "BANCO", "Banco de recursos"
        MANUAL = "MANUAL", "Agregada por el docente"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        CUMPLIDA = "CUMPLIDA", "Cumplida"

    tema_plan = models.ForeignKey(TemaPlan, on_delete=models.CASCADE, related_name="actividades")
    recurso = models.ForeignKey(
        RecursoRefuerzo, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    origen = models.CharField(max_length=10, choices=Origen.choices)
    titulo = models.CharField(max_length=200)
    instrucciones = models.TextField()
    duracion_minutos = models.PositiveSmallIntegerField(null=True, blank=True)
    nivel = models.CharField(max_length=10, choices=NivelActividad.choices, blank=True)
    estrategia = models.CharField(max_length=15, choices=EstrategiaRefuerzo.choices, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    cumplida_en = models.DateTimeField(null=True, blank=True)
    cumplida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "actividad de refuerzo"
        verbose_name_plural = "actividades de refuerzo"
        ordering = ["orden", "id"]

    def __str__(self):
        return self.titulo



def _almacen_evidencias():
    from django.core.files.storage import storages

    return storages["evidencias"]


def _ruta_evidencia(instancia, _nombre):
    actividad = instancia.actividad
    return f"plan-{actividad.tema_plan.plan_id}/actividad-{actividad.id}/{uuid.uuid4().hex}.jpg"


class EvidenciaActividad(models.Model):
    """
    Foto opcional que el representante sube como evidencia de una actividad de refuerzo
    hecha en casa. Se guarda re-codificada (JPEG, sin metadatos EXIF ni ubicación) en un
    almacenamiento privado; solo la ven el representante y el docente del plan.
    """

    actividad = models.ForeignKey(
        ActividadRefuerzo, on_delete=models.CASCADE, related_name="evidencias"
    )
    archivo = models.FileField(upload_to=_ruta_evidencia, storage=_almacen_evidencias, max_length=255)
    comentario = models.CharField(max_length=300, blank=True)
    tamano = models.PositiveIntegerField(help_text="Bytes del archivo guardado.")
    subida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "evidencia de actividad"
        verbose_name_plural = "evidencias de actividades"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Evidencia {self.id} de {self.actividad}"
