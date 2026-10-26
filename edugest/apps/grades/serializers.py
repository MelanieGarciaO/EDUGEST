from decimal import Decimal

from rest_framework import serializers

from apps.academic.models import Estudiante, Tema

from . import scale
from .models import Calificacion, CalificacionHistorial, Dificultad

MAX_CALIFICACIONES_POR_ENVIO = 100


class NivelMixin(serializers.Serializer):
    """Agrega el nivel cualitativo (código y nombre) calculado a partir de `valor`."""

    nivel = serializers.SerializerMethodField()
    nivel_nombre = serializers.SerializerMethodField()

    def get_nivel(self, obj):
        return scale.nivel_cualitativo(obj.valor)

    def get_nivel_nombre(self, obj):
        return scale.nombre_nivel(scale.nivel_cualitativo(obj.valor))


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
class CalificacionSerializer(NivelMixin, serializers.ModelSerializer):
    actividad_descripcion = serializers.CharField(source="actividad.descripcion", read_only=True)
    actividad_fecha_entrega = serializers.DateField(
        source="actividad.fecha_entrega", read_only=True
    )
    asignatura = serializers.IntegerField(
        source="actividad.asignacion.asignatura_id", read_only=True
    )
    asignatura_nombre = serializers.CharField(
        source="actividad.asignacion.asignatura.nombre", read_only=True
    )
    estudiante_nombre = serializers.CharField(source="estudiante.full_name", read_only=True)
    tema_nombre = serializers.CharField(source="tema.nombre", read_only=True)

    class Meta:
        model = Calificacion
        fields = (
            "id",
            "actividad",
            "actividad_descripcion",
            "actividad_fecha_entrega",
            "asignatura",
            "asignatura_nombre",
            "estudiante",
            "estudiante_nombre",
            "tema",
            "tema_nombre",
            "valor",
            "nivel",
            "nivel_nombre",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class HistorialSerializer(serializers.ModelSerializer):
    tema_anterior_nombre = serializers.CharField(source="tema_anterior.nombre", read_only=True)
    tema_nuevo_nombre = serializers.CharField(source="tema_nuevo.nombre", read_only=True)
    modificado_por_nombre = serializers.CharField(source="modificado_por.full_name", read_only=True)

    class Meta:
        model = CalificacionHistorial
        fields = (
            "id",
            "valor_anterior",
            "valor_nuevo",
            "tema_anterior",
            "tema_anterior_nombre",
            "tema_nuevo",
            "tema_nuevo_nombre",
            "modificado_por_nombre",
            "created_at",
        )
        read_only_fields = fields


class DificultadSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(source="estudiante.full_name", read_only=True)
    paralelo = serializers.IntegerField(source="estudiante.paralelo_id", read_only=True)
    paralelo_nombre = serializers.CharField(
        source="estudiante.paralelo.nombre_completo", read_only=True
    )
    tema_nombre = serializers.CharField(source="tema.nombre", read_only=True)
    asignatura = serializers.IntegerField(source="tema.asignatura_id", read_only=True)
    asignatura_nombre = serializers.CharField(source="tema.asignatura.nombre", read_only=True)
    promedio_nivel = serializers.SerializerMethodField()
    refuerzo = serializers.SerializerMethodField()
    reincidente = serializers.BooleanField(read_only=True)

    class Meta:
        model = Dificultad
        fields = (
            "id",
            "estudiante",
            "estudiante_nombre",
            "paralelo",
            "paralelo_nombre",
            "tema",
            "tema_nombre",
            "asignatura",
            "asignatura_nombre",
            "promedio",
            "promedio_nivel",
            "num_calificaciones",
            "nivel",
            "estado",
            "detectada_en",
            "superada_en",
            "veces_detectada",
            "reincidente",
            "updated_at",
            "refuerzo",
        )
        read_only_fields = fields

    def get_promedio_nivel(self, obj):
        return scale.nombre_nivel(scale.nivel_cualitativo(obj.promedio))

    def get_refuerzo(self, obj):
        """EN_CURSO (plan vigente), PENDIENTE_EVALUACION (plan completado sin evaluar) o None."""
        if getattr(obj, "refuerzo_en_curso", False):
            return "EN_CURSO"
        if getattr(obj, "refuerzo_pendiente_evaluacion", False):
            return "PENDIENTE_EVALUACION"
        return None


# ---------------------------------------------------------------------------
# Entrada: guardado masivo de notas de una actividad
# ---------------------------------------------------------------------------
class ItemCalificacionSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField(min_value=1)
    valor = serializers.DecimalField(
        max_digits=4,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("10"),
        error_messages={"max_decimal_places": "Usa como máximo 2 decimales."},
    )


class GuardarCalificacionesSerializer(serializers.Serializer):
    """Requiere en el contexto la `actividad` sobre la que se califica."""

    tema = serializers.PrimaryKeyRelatedField(
        queryset=Tema.objects.filter(is_active=True),
        error_messages={"does_not_exist": "El tema no existe o está inactivo."},
    )
    calificaciones = ItemCalificacionSerializer(
        many=True, allow_empty=False, max_length=MAX_CALIFICACIONES_POR_ENVIO
    )

    def validate(self, attrs):
        actividad = self.context["actividad"]
        asignacion = actividad.asignacion

        tema = attrs["tema"]
        if (
            tema.asignatura_id != asignacion.asignatura_id
            or tema.grado_id != asignacion.paralelo.grado_id
        ):
            raise serializers.ValidationError(
                {"tema": "El tema no corresponde al grado y la asignatura de la actividad."}
            )

        ids = [item["estudiante"] for item in attrs["calificaciones"]]
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        if repetidos:
            raise serializers.ValidationError(
                {"calificaciones": f"Estudiantes repetidos en el envío: {repetidos}."}
            )

        validos = set(
            Estudiante.objects.filter(
                paralelo_id=asignacion.paralelo_id, is_active=True, id__in=ids
            ).values_list("id", flat=True)
        )
        invalidos = sorted(set(ids) - validos)
        if invalidos:
            raise serializers.ValidationError(
                {
                    "calificaciones": "Estudiantes inexistentes, inactivos o de otro paralelo: "
                    f"{invalidos}."
                }
            )
        return attrs
