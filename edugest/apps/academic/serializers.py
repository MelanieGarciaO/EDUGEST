from rest_framework import serializers

from apps.security.models import Role, User

from .grados import grado_habilitado, mensaje_grado_no_habilitado
from .models import Asignatura, AsignacionDocente, Estudiante, Grado, Paralelo, Tema


class GradoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grado
        fields = ("id", "nombre", "orden")


class ParaleloSerializer(serializers.ModelSerializer):
    grado_nombre = serializers.CharField(source="grado.nombre", read_only=True)
    nombre_completo = serializers.CharField(read_only=True)
    estudiantes_count = serializers.SerializerMethodField()

    class Meta:
        model = Paralelo
        fields = (
            "id",
            "grado",
            "grado_nombre",
            "nombre",
            "nombre_completo",
            "is_active",
            "estudiantes_count",
        )

    def get_estudiantes_count(self, obj):
        # El representante no necesita (ni debe) conocer el tamaño total del paralelo.
        request = self.context.get("request")
        if request and request.user.role == Role.REPRESENTANTE:
            return None
        return obj.estudiantes.filter(is_active=True).count()

    def validate_nombre(self, value):
        return value.strip().upper()

    def validate_grado(self, value):
        cambia = self.instance is None or value.pk != self.instance.grado_id
        if cambia and not grado_habilitado(value):
            raise serializers.ValidationError(mensaje_grado_no_habilitado())
        return value

    def validate_is_active(self, value):
        if value is False and self.instance is not None:
            if self.instance.estudiantes.filter(is_active=True).exists():
                raise serializers.ValidationError(
                    "No puedes desactivar un paralelo con estudiantes activos."
                )
            if self.instance.asignaciones.filter(is_active=True).exists():
                raise serializers.ValidationError(
                    "No puedes desactivar un paralelo con asignaciones docentes activas."
                )
        return value


class AsignaturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asignatura
        fields = ("id", "nombre", "is_active")

    def validate_nombre(self, value):
        value = value.strip()
        qs = Asignatura.objects.filter(nombre__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una asignatura con ese nombre.")
        return value

    def validate_is_active(self, value):
        if (
            value is False
            and self.instance is not None
            and self.instance.asignaciones.filter(is_active=True).exists()
        ):
            raise serializers.ValidationError(
                "No puedes desactivar una asignatura con asignaciones docentes activas."
            )
        return value


class EstudianteSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    paralelo = serializers.PrimaryKeyRelatedField(
        queryset=Paralelo.objects.filter(is_active=True),
        error_messages={"does_not_exist": "El paralelo no existe o está inactivo."},
    )
    paralelo_nombre = serializers.CharField(source="paralelo.nombre_completo", read_only=True)
    grado_nombre = serializers.CharField(source="paralelo.grado.nombre", read_only=True)
    representante = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.REPRESENTANTE, is_active=True),
        error_messages={
            "does_not_exist": "El representante no existe, está inactivo o no tiene rol de representante."
        },
    )
    representante_nombre = serializers.CharField(source="representante.full_name", read_only=True)

    class Meta:
        model = Estudiante
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "paralelo",
            "paralelo_nombre",
            "grado_nombre",
            "representante",
            "representante_nombre",
            "is_active",
        )

    def validate_paralelo(self, value):
        cambia = self.instance is None or value.pk != self.instance.paralelo_id
        if cambia and not grado_habilitado(value.grado):
            raise serializers.ValidationError(mensaje_grado_no_habilitado())
        return value


class AsignacionDocenteSerializer(serializers.ModelSerializer):
    docente = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Role.DOCENTE, is_active=True),
        error_messages={
            "does_not_exist": "El docente no existe, está inactivo o no tiene rol de docente."
        },
    )
    docente_nombre = serializers.CharField(source="docente.full_name", read_only=True)
    paralelo = serializers.PrimaryKeyRelatedField(
        queryset=Paralelo.objects.filter(is_active=True),
        error_messages={"does_not_exist": "El paralelo no existe o está inactivo."},
    )
    paralelo_nombre = serializers.CharField(source="paralelo.nombre_completo", read_only=True)
    asignatura = serializers.PrimaryKeyRelatedField(
        queryset=Asignatura.objects.filter(is_active=True),
        error_messages={"does_not_exist": "La asignatura no existe o está inactiva."},
    )
    asignatura_nombre = serializers.CharField(source="asignatura.nombre", read_only=True)

    class Meta:
        model = AsignacionDocente
        fields = (
            "id",
            "docente",
            "docente_nombre",
            "paralelo",
            "paralelo_nombre",
            "asignatura",
            "asignatura_nombre",
            "is_active",
        )
        # Los validadores únicos se declaran a mano porque los campos están redefinidos.
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=AsignacionDocente.objects.all(),
                fields=("paralelo", "asignatura"),
                message="Ya existe un docente asignado a esa asignatura en ese paralelo. Edita la asignación existente.",
            )
        ]

    def validate_paralelo(self, value):
        cambia = self.instance is None or value.pk != self.instance.paralelo_id
        if cambia and not grado_habilitado(value.grado):
            raise serializers.ValidationError(mensaje_grado_no_habilitado())
        return value


class TemaSerializer(serializers.ModelSerializer):
    grado = serializers.PrimaryKeyRelatedField(queryset=Grado.objects.all())
    grado_nombre = serializers.CharField(source="grado.nombre", read_only=True)
    asignatura = serializers.PrimaryKeyRelatedField(
        queryset=Asignatura.objects.filter(is_active=True),
        error_messages={"does_not_exist": "La asignatura no existe o está inactiva."},
    )
    asignatura_nombre = serializers.CharField(source="asignatura.nombre", read_only=True)
    padre = serializers.PrimaryKeyRelatedField(
        queryset=Tema.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "El tema padre no existe o está inactivo."},
    )
    padre_nombre = serializers.CharField(source="padre.nombre", read_only=True, allow_null=True)
    es_subtema = serializers.BooleanField(read_only=True)

    class Meta:
        model = Tema
        fields = (
            "id",
            "grado",
            "grado_nombre",
            "asignatura",
            "asignatura_nombre",
            "padre",
            "padre_nombre",
            "nombre",
            "es_subtema",
            "is_active",
        )
        # La unicidad (con condiciones, por ser el padre opcional) se valida a mano en
        # `validate`; los validadores automáticos de DRF exigirían el campo `padre`.
        validators = []

    def validate_nombre(self, value):
        return " ".join(value.split())

    def validate_grado(self, value):
        # Solo se controla al crear: el grado de un tema existente no se puede cambiar.
        if self.instance is None and not grado_habilitado(value):
            raise serializers.ValidationError(mensaje_grado_no_habilitado())
        return value

    def validate_is_active(self, value):
        if (
            value is False
            and self.instance is not None
            and self.instance.subtemas.filter(is_active=True).exists()
        ):
            raise serializers.ValidationError(
                "No puedes desactivar un tema que tiene subtemas activos."
            )
        return value

    def validate(self, attrs):
        inst = self.instance

        # Una vez creado, el tema no cambia de lugar: las calificaciones dependen de él.
        if inst is not None:
            for campo in ("grado", "asignatura", "padre"):
                if campo in attrs and attrs[campo] != getattr(inst, campo):
                    raise serializers.ValidationError(
                        {campo: "Este dato no se puede cambiar una vez creado el tema."}
                    )

        grado = attrs.get("grado", inst.grado if inst else None)
        asignatura = attrs.get("asignatura", inst.asignatura if inst else None)
        padre = attrs["padre"] if "padre" in attrs else (inst.padre if inst else None)
        nombre = attrs.get("nombre", inst.nombre if inst else None)

        if padre is not None:
            if padre.padre_id is not None:
                raise serializers.ValidationError({"padre": "Un subtema no puede tener subtemas."})
            if padre.grado_id != grado.id or padre.asignatura_id != asignatura.id:
                raise serializers.ValidationError(
                    {"padre": "El tema padre debe ser del mismo grado y asignatura."}
                )

        duplicados = Tema.objects.filter(
            grado=grado, asignatura=asignatura, padre=padre, nombre__iexact=nombre
        )
        if inst is not None:
            duplicados = duplicados.exclude(pk=inst.pk)
        if duplicados.exists():
            raise serializers.ValidationError(
                {"nombre": "Ya existe un tema con ese nombre en este nivel."}
            )
        return attrs
