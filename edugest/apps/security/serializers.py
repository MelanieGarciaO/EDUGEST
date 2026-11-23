from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, User
from .validadores import nombre_persona


TIPOS_CORREO_ACCESO = ("cuenta_creada", "acceso_reenviado", "acceso_renovado")  # = avisos.TIPOS_ACCESO


class UserSerializer(serializers.ModelSerializer):
    """Representación de lectura de un usuario."""

    full_name = serializers.CharField(read_only=True)
    debe_aceptar_terminos = serializers.SerializerMethodField()
    # Para el admin: cuenta creada que aún no se activa y si el correo de acceso llegó.
    acceso_pendiente = serializers.SerializerMethodField()
    correo_acceso = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "must_change_password",
            "clave_temporal_expira_en",
            "debe_aceptar_terminos",
            "terminos_version",
            "terminos_aceptados_en",
            "date_joined",
            "last_login",
            "acceso_pendiente",
            "correo_acceso",
        )
        read_only_fields = fields

    def get_debe_aceptar_terminos(self, user):
        return user.terminos_version != settings.LEGAL_VERSION

    def get_acceso_pendiente(self, user):
        """Nunca ingresó y tiene la contraseña temporal del correo de bienvenida."""
        return bool(user.must_change_password and user.last_login is None)

    def get_correo_acceso(self, user):
        """Estado del correo de acceso: EN_COLA | ENVIADO | ERROR | PENDIENTE | None (sin registro)."""
        if not self.get_acceso_pendiente(user):
            return None
        if hasattr(user, "estado_correo_acceso"):  # anotado en la lista (sin consultas extra)
            return "EN_COLA" if getattr(user, "envio_en_cola", False) else user.estado_correo_acceso
        from .models import EnvioAcceso

        if EnvioAcceso.objects.filter(usuario=user, estado__in=("PENDIENTE", "ENVIANDO")).exists():
            return "EN_COLA"  # importado: su correo de acceso aún está en la cola
        from apps.notifications.models import Notificacion

        return (
            Notificacion.objects.filter(usuario=user, tipo__in=TIPOS_CORREO_ACCESO)
            .order_by("-created_at", "-id").values_list("estado_correo", flat=True).first()
        )


class LoginSerializer(TokenObtainPairSerializer):
    """Login con correo y contraseña. Agrega datos del usuario a los tokens y a la respuesta."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["full_name"] = user.full_name
        token["must_change_password"] = user.must_change_password
        return token

    def validate(self, attrs):
        # Contraseña temporal de bienvenida correcta pero vencida: se envía otra por correo.
        from .recuperacion import renovar_si_vencio

        email = (attrs.get(self.username_field) or "").strip()
        renovar_si_vencio(User.objects.filter(email__iexact=email).first(), attrs.get("password") or "")
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def save(self, **kwargs):
        try:
            RefreshToken(self.validated_data["refresh"]).blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "El token no es válido o ya fue invalidado."}
            )


class ChangePasswordSerializer(serializers.Serializer):
    """
    La validación de la clave temporal y de la contraseña nueva la hace
    recuperacion.cambiar_clave (primer acceso, cuenta recuperada o cambio desde el Perfil).
    """

    clave_temporal = serializers.CharField(write_only=True, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class RestablecerSerializer(serializers.Serializer):
    email = serializers.EmailField()
    clave_temporal = serializers.CharField(trim_whitespace=True)
    new_password = serializers.CharField(trim_whitespace=False)


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Alta de usuarios por el administrador. El sistema genera una contraseña temporal y la
    envía SOLO al correo del usuario: el administrador no la ve ni puede fijar una.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")

    def validate_first_name(self, value):
        return nombre_persona(value, "nombres")

    def validate_last_name(self, value):
        return nombre_persona(value, "apellidos")

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def create(self, validated_data):
        from .recuperacion import asignar_clave_bienvenida

        usuario = User.objects.create_user(password=None, must_change_password=True, **validated_data)
        asignar_clave_bienvenida(usuario)  # vence en 2 horas y solo viaja por correo
        return usuario

    def to_representation(self, instance):
        return UserSerializer(instance).data


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")

    def validate_first_name(self, value):
        return nombre_persona(value, "nombres")

    def validate_last_name(self, value):
        return nombre_persona(value, "apellidos")

    def validate_email(self, value):
        value = value.lower()
        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def validate_role(self, value):
        request = self.context.get("request")
        if (
            request
            and self.instance == request.user
            and value != Role.ADMINISTRADOR
        ):
            raise serializers.ValidationError(
                "No puedes quitarte a ti mismo el rol de administrador."
            )
        return value

    def to_representation(self, instance):
        return UserSerializer(instance).data


class AceptarTerminosSerializer(serializers.Serializer):
    """El usuario acepta la versión vigente de los términos y la política de privacidad."""

    version = serializers.CharField(max_length=20)
    acepto = serializers.BooleanField()

    def validate_version(self, value):
        if value != settings.LEGAL_VERSION:
            raise serializers.ValidationError(
                "Los términos se actualizaron. Recarga la página para leer la versión vigente."
            )
        return value

    def validate_acepto(self, value):
        if not value:
            raise serializers.ValidationError("Debes aceptar los términos para continuar.")
        return value
