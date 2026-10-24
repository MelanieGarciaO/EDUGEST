from rest_framework import serializers

from apps.academic.models import Asignatura, Tema
from apps.grades.models import Dificultad
from apps.security.models import Role

from . import selectors
from .models import ActividadRefuerzo, EstrategiaRefuerzo, PlanRefuerzo, RecursoRefuerzo, TemaPlan


# ---------------------------------------------------------------------------
# Lectura de planes
# ---------------------------------------------------------------------------
class ActividadRefuerzoSerializer(serializers.ModelSerializer):
    cumplida_por_nombre = serializers.CharField(
        source="cumplida_por.full_name", read_only=True, allow_null=True
    )

    class Meta:
        model = ActividadRefuerzo
        fields = (
            "id",
            "recurso",
            "origen",
            "titulo",
            "instrucciones",
            "duracion_minutos",
            "nivel",
            "estrategia",
            "orden",
            "estado",
            "cumplida_en",
            "cumplida_por",
            "cumplida_por_nombre",
        )
        read_only_fields = fields


class TemaPlanSerializer(serializers.ModelSerializer):
    tema_nombre = serializers.CharField(source="tema.nombre", read_only=True)
    dificultad_estado = serializers.CharField(
        source="dificultad.estado", read_only=True, allow_null=True, default=None
    )
    dificultad_reincidente = serializers.BooleanField(
        source="dificultad.reincidente", read_only=True, default=False
    )
    actividades = ActividadRefuerzoSerializer(many=True, read_only=True)
    nota_evaluacion = serializers.DecimalField(
        source="evaluacion.valor", max_digits=4, decimal_places=2, read_only=True, allow_null=True, default=None
    )
    evaluacion_actividad = serializers.IntegerField(
        source="evaluacion.actividad_id", read_only=True, allow_null=True, default=None
    )
    evaluacion_fecha = serializers.DateField(
        source="evaluacion.actividad.fecha_entrega", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = TemaPlan
        fields = (
            "id",
            "tema",
            "tema_nombre",
            "orden",
            "origen",
            "motivo",
            "objetivo",
            "promedio_inicial",
            "nivel_dificultad",
            "dificultad_estado",
            "dificultad_reincidente",
            "sin_recursos",
            "actividades",
            "nota_evaluacion",
            "evaluacion_actividad",
            "evaluacion_fecha",
            "promedio_final",
            "superado",
            "evaluado_en",
        )
        read_only_fields = fields


class PlanSerializer(serializers.ModelSerializer):
    estudiante_nombre = serializers.CharField(source="estudiante.full_name", read_only=True)
    paralelo_nombre = serializers.CharField(
        source="estudiante.paralelo.nombre_completo", read_only=True
    )
    asignatura_nombre = serializers.CharField(source="asignatura.nombre", read_only=True)
    docente_nombre = serializers.CharField(source="docente.full_name", read_only=True)
    temas = TemaPlanSerializer(many=True, read_only=True)
    avance = serializers.SerializerMethodField()
    evaluacion = serializers.SerializerMethodField()
    revisado_por_nombre = serializers.CharField(
        source="revisado_por.full_name", read_only=True, allow_null=True, default=None
    )

    class Meta:
        model = PlanRefuerzo
        fields = (
            "id",
            "estudiante",
            "estudiante_nombre",
            "paralelo_nombre",
            "asignatura",
            "asignatura_nombre",
            "docente",
            "docente_nombre",
            "nivel",
            "estado",
            "avance",
            "evaluacion",
            "temas",
            "aprobado_en",
            "completado_en",
            "cancelado_en",
            "revisado_en",
            "revisado_por_nombre",
            "created_at",
        )
        read_only_fields = fields

    def get_avance(self, plan):
        """Actividades cumplidas y temas superados (según las notas nuevas del módulo grades)."""
        temas = list(plan.temas.all())
        actividades = [a for t in temas for a in t.actividades.all()]
        total = len(actividades)
        cumplidas = sum(1 for a in actividades if a.estado == ActividadRefuerzo.Estado.CUMPLIDA)
        return {
            "actividades_total": total,
            "actividades_cumplidas": cumplidas,
            "porcentaje": round(100 * cumplidas / total) if total else 0,
            "temas_total": len(temas),
            "temas_superados": sum(1 for t in temas if self._tema_superado(t)),
        }

    def get_evaluacion(self, plan):
        """
        Estado de la evaluación de refuerzo (solo para planes completados):
        PENDIENTE (ningún tema evaluado), PARCIAL o EVALUADO; y el resultado cuando ya
        se evaluaron todos: SUPERADO (todos los temas) o NO_SUPERADO.
        """
        if plan.estado != PlanRefuerzo.Estado.COMPLETADA:
            return None
        temas = list(plan.temas.all())
        evaluados = [t for t in temas if t.superado is not None]
        superados = sum(1 for t in evaluados if t.superado)
        if not evaluados:
            estado = "PENDIENTE"
        elif len(evaluados) < len(temas):
            estado = "PARCIAL"
        else:
            estado = "EVALUADO"
        resultado = None
        if estado == "EVALUADO":
            resultado = "SUPERADO" if superados == len(temas) else "NO_SUPERADO"
        return {
            "estado": estado,
            "resultado": resultado,
            "temas_total": len(temas),
            "temas_evaluados": len(evaluados),
            "temas_superados": superados,
        }

    @staticmethod
    def _tema_superado(tema_plan):
        """
        Si el tema ya tiene evaluación de refuerzo, manda su resultado. Si no: con dificultad
        detectada, si la superó con notas nuevas; refuerzo manual, si cumplió sus actividades.
        """
        if tema_plan.superado is not None:
            return tema_plan.superado
        if tema_plan.dificultad is not None:
            return tema_plan.dificultad.estado == Dificultad.Estado.SUPERADA
        actividades = list(tema_plan.actividades.all())
        return bool(actividades) and all(
            a.estado == ActividadRefuerzo.Estado.CUMPLIDA for a in actividades
        )


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------
class TemaManualSerializer(serializers.Serializer):
    """Un tema que el docente pide reforzar aunque no tenga dificultad detectada."""

    tema = serializers.PrimaryKeyRelatedField(
        queryset=Tema.objects.filter(is_active=True),
        error_messages={"does_not_exist": "El tema no existe o está inactivo."},
    )
    motivo = serializers.CharField(
        max_length=300,
        error_messages={"blank": "Indica por qué se refuerza este tema (por ejemplo, la destreza que falla)."},
    )


class GenerarPlanSerializer(serializers.Serializer):
    estudiante = serializers.IntegerField(min_value=1)
    asignatura = serializers.PrimaryKeyRelatedField(
        queryset=Asignatura.objects.filter(is_active=True),
        error_messages={"does_not_exist": "La asignatura no existe o está inactiva."},
    )
    temas_manuales = TemaManualSerializer(many=True, required=False)


class TemaPlanEditarSerializer(serializers.ModelSerializer):
    objetivo = serializers.CharField(max_length=500)

    class Meta:
        model = TemaPlan
        fields = ("objetivo",)

    def validate_objetivo(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El objetivo no puede estar vacío.")
        return value


class AgregarActividadSerializer(serializers.Serializer):
    """Agrega una actividad desde el banco (`recurso`) o una propia (`titulo` + `instrucciones`)."""

    recurso = serializers.PrimaryKeyRelatedField(
        queryset=RecursoRefuerzo.objects.filter(is_active=True).select_related("tema"),
        required=False,
        error_messages={"does_not_exist": "El recurso no existe o está inactivo."},
    )
    titulo = serializers.CharField(max_length=200, required=False)
    instrucciones = serializers.CharField(max_length=2000, required=False)
    duracion_minutos = serializers.IntegerField(
        min_value=1, max_value=240, required=False, allow_null=True
    )
    estrategia = serializers.ChoiceField(
        choices=EstrategiaRefuerzo.choices, required=False, allow_blank=True
    )

    def validate(self, attrs):
        if "recurso" not in attrs:
            faltan = {c: "Este campo es requerido." for c in ("titulo", "instrucciones") if c not in attrs}
            if faltan:
                raise serializers.ValidationError(
                    {**faltan, "recurso": "Indica un recurso del banco o los datos de una actividad propia."}
                )
        return attrs


class ActividadRefuerzoEditarSerializer(serializers.ModelSerializer):
    estrategia = serializers.ChoiceField(
        choices=EstrategiaRefuerzo.choices, required=False, allow_blank=True
    )
    titulo = serializers.CharField(max_length=200, required=False)
    instrucciones = serializers.CharField(max_length=2000, required=False)
    duracion_minutos = serializers.IntegerField(
        min_value=1, max_value=240, required=False, allow_null=True
    )

    class Meta:
        model = ActividadRefuerzo
        fields = ("titulo", "instrucciones", "duracion_minutos", "estrategia")

    def validate_titulo(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El título no puede estar vacío.")
        return value


# ---------------------------------------------------------------------------
# Banco de recursos
# ---------------------------------------------------------------------------
class RecursoSerializer(serializers.ModelSerializer):
    tema = serializers.PrimaryKeyRelatedField(
        queryset=Tema.objects.filter(is_active=True),
        error_messages={"does_not_exist": "El tema no existe o está inactivo."},
    )
    tema_nombre = serializers.CharField(source="tema.nombre", read_only=True)
    asignatura = serializers.IntegerField(source="tema.asignatura_id", read_only=True)
    asignatura_nombre = serializers.CharField(source="tema.asignatura.nombre", read_only=True)
    grado = serializers.IntegerField(source="tema.grado_id", read_only=True)
    grado_nombre = serializers.CharField(source="tema.grado.nombre", read_only=True)
    creado_por_nombre = serializers.CharField(
        source="creado_por.full_name", read_only=True, allow_null=True
    )
    instrucciones = serializers.CharField(max_length=2000)

    class Meta:
        model = RecursoRefuerzo
        fields = (
            "id",
            "tema",
            "tema_nombre",
            "asignatura",
            "asignatura_nombre",
            "grado",
            "grado_nombre",
            "nivel",
            "estrategia",
            "titulo",
            "instrucciones",
            "duracion_minutos",
            "is_active",
            "creado_por",
            "creado_por_nombre",
            "created_at",
        )
        read_only_fields = ("id", "creado_por", "created_at")
        validators = []  # la unicidad se valida a mano, sin distinguir mayúsculas

    def validate_titulo(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("El título no puede estar vacío.")
        return value

    def validate(self, attrs):
        inst = self.instance
        request = self.context["request"]

        if inst is not None and "tema" in attrs and attrs["tema"] != inst.tema:
            raise serializers.ValidationError(
                {"tema": "El tema de un recurso no se puede cambiar una vez creado."}
            )

        tema = attrs.get("tema", inst.tema if inst else None)
        titulo = attrs.get("titulo", inst.titulo if inst else None)

        if inst is None and request.user.role == Role.DOCENTE:
            if not selectors.docente_imparte_en_grado(request.user, tema.asignatura_id, tema.grado_id):
                raise serializers.ValidationError(
                    {"tema": "Solo puedes cargar recursos de las asignaturas y grados que impartes."}
                )

        # Se compara en Python (casefold) para que mayúsculas y tildes se traten igual en
        # cualquier motor de base de datos.
        existentes = RecursoRefuerzo.objects.filter(tema=tema)
        if inst is not None:
            existentes = existentes.exclude(pk=inst.pk)
        if titulo.casefold() in {t.casefold() for t in existentes.values_list("titulo", flat=True)}:
            raise serializers.ValidationError({"titulo": "Ya existe un recurso con ese título en este tema."})
        return attrs
