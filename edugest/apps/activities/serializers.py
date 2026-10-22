from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.academic.models import Asignatura, AsignacionDocente, Paralelo
from apps.grades import scale

from . import clock
from .models import SIN_HORA, Actividad, Extraccion
from .signals import actividad_modificada, actividad_publicada

MAX_MATERIALES = 20
MAX_TEXTO = 2000


# ---------------------------------------------------------------------------
# Campos con alcance por docente
# ---------------------------------------------------------------------------
class ParaleloDelDocenteField(serializers.PrimaryKeyRelatedField):
    """Solo acepta paralelos donde el docente autenticado tiene una asignación activa."""

    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", Paralelo.objects.none())
        kwargs.setdefault(
            "error_messages",
            {"does_not_exist": "No impartes clases en ese paralelo o no existe."},
        )
        super().__init__(**kwargs)

    def get_queryset(self):
        user = self.context["request"].user
        return Paralelo.objects.filter(
            is_active=True, asignaciones__docente=user, asignaciones__is_active=True
        ).distinct()


class ExtraccionDelDocenteField(serializers.PrimaryKeyRelatedField):
    """Solo acepta extracciones propias que aún no se han convertido en actividad."""

    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", Extraccion.objects.none())
        kwargs.setdefault(
            "error_messages",
            {"does_not_exist": "La extracción no existe o ya fue utilizada."},
        )
        super().__init__(**kwargs)

    def get_queryset(self):
        user = self.context["request"].user
        return Extraccion.objects.filter(docente=user, actividad__isnull=True)


# ---------------------------------------------------------------------------
# Utilidades de validación
# ---------------------------------------------------------------------------
def limpiar_materiales(valores):
    """Recorta espacios, descarta vacíos y elimina repetidos conservando el orden."""
    limpios, vistos = [], set()
    for valor in valores:
        item = " ".join(valor.split())
        if item and item.lower() not in vistos:
            vistos.add(item.lower())
            limpios.append(item)
    return limpios


def validar_fecha_futura(valor):
    if valor < timezone.localdate():
        raise serializers.ValidationError("La fecha de entrega no puede ser anterior a hoy.")
    return valor


def validar_hora_no_pasada(fecha, hora):
    """Si la entrega es hoy y se fija una hora, esa hora no puede haber pasado ya."""
    if hora != SIN_HORA and fecha == timezone.localdate() and hora <= clock.hora_actual():
        raise serializers.ValidationError({"hora_entrega": "La hora de entrega de hoy ya pasó."})


def hora_field(**kwargs):
    """Hora opcional: vacía o nula equivale a 00:00 (sin hora específica)."""
    return serializers.TimeField(required=False, allow_null=True, **kwargs)


def materiales_field():
    return serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=True),
        required=False,
        max_length=MAX_MATERIALES,
    )


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
class ActividadSerializer(serializers.ModelSerializer):
    asignatura = serializers.IntegerField(source="asignacion.asignatura_id", read_only=True)
    asignatura_nombre = serializers.CharField(source="asignacion.asignatura.nombre", read_only=True)
    paralelo = serializers.IntegerField(source="asignacion.paralelo_id", read_only=True)
    paralelo_nombre = serializers.CharField(
        source="asignacion.paralelo.nombre_completo", read_only=True
    )
    docente = serializers.IntegerField(source="asignacion.docente_id", read_only=True)
    docente_nombre = serializers.CharField(source="asignacion.docente.full_name", read_only=True)
    vigencia = serializers.SerializerMethodField()
    notas = serializers.SerializerMethodField()

    class Meta:
        model = Actividad
        fields = (
            "id",
            "asignatura",
            "asignatura_nombre",
            "paralelo",
            "paralelo_nombre",
            "docente",
            "docente_nombre",
            "descripcion",
            "fecha_entrega",
            "hora_entrega",
            "materiales",
            "tema",
            "es_evaluacion_refuerzo",
            "estado",
            "vigencia",
            "created_at",
            "updated_at",
            "cancelada_en",
            "notas",
        )
        read_only_fields = fields

    def get_vigencia(self, obj):
        return obj.vigencia()

    def get_notas(self, obj):
        """
        Notas de la actividad que puede ver el representante (solo de sus estudiantes).
        Para otros roles es None: el docente las consulta en «Calificar».
        La vista las precarga en `notas_representante` para evitar una consulta por fila.
        """
        notas = getattr(obj, "notas_representante", None)
        if notas is None:
            return None
        return [
            {
                "estudiante": c.estudiante_id,
                "estudiante_nombre": c.estudiante.full_name,
                "tema_nombre": c.tema.nombre,
                "valor": str(c.valor),
                "nivel": scale.nivel_cualitativo(c.valor),
                "nivel_nombre": scale.nombre_nivel(scale.nivel_cualitativo(c.valor)),
                "fecha": c.updated_at,
            }
            for c in notas
        ]


# ---------------------------------------------------------------------------
# Vista previa (PLN)
# ---------------------------------------------------------------------------
class PrevisualizarSerializer(serializers.Serializer):
    paralelo = ParaleloDelDocenteField()
    texto = serializers.CharField(min_length=3, max_length=MAX_TEXTO)


# ---------------------------------------------------------------------------
# Publicación
# ---------------------------------------------------------------------------
class ActividadCrearSerializer(serializers.Serializer):
    paralelo = ParaleloDelDocenteField()
    asignatura = serializers.PrimaryKeyRelatedField(
        queryset=Asignatura.objects.filter(is_active=True),
        error_messages={"does_not_exist": "La asignatura no existe o está inactiva."},
    )
    descripcion = serializers.CharField(max_length=MAX_TEXTO)
    fecha_entrega = serializers.DateField(validators=[validar_fecha_futura])
    hora_entrega = hora_field()
    materiales = materiales_field()
    tema = serializers.CharField(max_length=150, required=False, allow_blank=True)
    es_evaluacion_refuerzo = serializers.BooleanField(required=False, default=False)
    extraccion = ExtraccionDelDocenteField(required=False, allow_null=True)

    def validate_materiales(self, value):
        return limpiar_materiales(value)

    def validate_tema(self, value):
        return " ".join(value.split())

    def validate(self, attrs):
        attrs["hora_entrega"] = attrs.get("hora_entrega") or SIN_HORA
        validar_hora_no_pasada(attrs["fecha_entrega"], attrs["hora_entrega"])
        user = self.context["request"].user
        asignacion = AsignacionDocente.objects.filter(
            docente=user,
            paralelo=attrs["paralelo"],
            asignatura=attrs["asignatura"],
            is_active=True,
        ).first()
        if asignacion is None:
            raise serializers.ValidationError(
                {"asignatura": "No impartes esa asignatura en este paralelo."}
            )
        extraccion = attrs.get("extraccion")
        if extraccion is not None and extraccion.paralelo_id != attrs["paralelo"].id:
            raise serializers.ValidationError(
                {"extraccion": "La extracción corresponde a otro paralelo."}
            )
        attrs["asignacion"] = asignacion
        return attrs

    def create(self, validated_data):
        extraccion = validated_data.get("extraccion")
        try:
            with transaction.atomic():
                actividad = Actividad.objects.create(
                    asignacion=validated_data["asignacion"],
                    creada_por=self.context["request"].user,
                    descripcion=validated_data["descripcion"].strip(),
                    fecha_entrega=validated_data["fecha_entrega"],
                    hora_entrega=validated_data["hora_entrega"],
                    materiales=validated_data.get("materiales", []),
                    tema=validated_data.get("tema", ""),
                    es_evaluacion_refuerzo=validated_data.get("es_evaluacion_refuerzo", False),
                    texto_original=extraccion.texto_original if extraccion else "",
                    extraccion=extraccion,
                )
        except IntegrityError:
            # Dos publicaciones simultáneas con la misma extracción.
            raise serializers.ValidationError(
                {"extraccion": "La extracción ya fue utilizada."}
            )
        transaction.on_commit(
            lambda: actividad_publicada.send(sender=Actividad, actividad=actividad)
        )
        return actividad

    def to_representation(self, instance):
        return ActividadSerializer(instance, context=self.context).data


# ---------------------------------------------------------------------------
# Edición
# ---------------------------------------------------------------------------
class ActividadEditarSerializer(serializers.ModelSerializer):
    """Solo se pueden editar estos campos; el paralelo y la asignatura no cambian."""

    descripcion = serializers.CharField(max_length=MAX_TEXTO, required=False)
    fecha_entrega = serializers.DateField(required=False, validators=[validar_fecha_futura])
    hora_entrega = hora_field()
    materiales = materiales_field()
    tema = serializers.CharField(max_length=150, required=False, allow_blank=True)

    class Meta:
        model = Actividad
        fields = (
            "descripcion",
            "fecha_entrega",
            "hora_entrega",
            "materiales",
            "tema",
            "es_evaluacion_refuerzo",
        )

    def validate_materiales(self, value):
        return limpiar_materiales(value)

    def validate_tema(self, value):
        return " ".join(value.split())

    def validate(self, attrs):
        actividad = self.instance
        if actividad.estado == Actividad.Estado.CANCELADA:
            raise serializers.ValidationError("No se puede editar una actividad cancelada.")
        if actividad.vencida():
            raise serializers.ValidationError(
                "No se puede editar una actividad cuyo plazo de entrega ya venció."
            )
        if "hora_entrega" in attrs:
            attrs["hora_entrega"] = attrs["hora_entrega"] or SIN_HORA
        # Se valida el resultado final: la fecha y la hora que quedarían tras la edición.
        validar_hora_no_pasada(
            attrs.get("fecha_entrega", actividad.fecha_entrega),
            attrs.get("hora_entrega", actividad.hora_entrega),
        )
        return attrs

    def update(self, instance, validated_data):
        if "descripcion" in validated_data:
            validated_data["descripcion"] = validated_data["descripcion"].strip()
        cambios = [
            campo for campo, valor in validated_data.items() if getattr(instance, campo) != valor
        ]
        if not cambios:
            return instance
        for campo in cambios:
            setattr(instance, campo, validated_data[campo])
        instance.save()
        transaction.on_commit(
            lambda: actividad_modificada.send(
                sender=Actividad, actividad=instance, campos=cambios
            )
        )
        return instance

    def to_representation(self, instance):
        return ActividadSerializer(instance, context=self.context).data
