from django.conf import settings
from django.contrib.auth.password_validation import (
    validate_password as django_validate_password,
)
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, User
from .utils import generate_temporary_password


class UserSerializer(serializers.ModelSerializer):
    """Representación de lectura de un usuario."""

    full_name = serializers.CharField(read_only=True)
    debe_aceptar_terminos = serializers.SerializerMethodField()

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
            "debe_aceptar_terminos",
            "terminos_version",
            "terminos_aceptados_en",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields

    def get_debe_aceptar_terminos(self, user):
        return user.terminos_version != settings.LEGAL_VERSION


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
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("La contraseña actual es incorrecta.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "La nueva contraseña debe ser distinta de la actual."}
            )
        django_validate_password(attrs["new_password"], user)
        return attrs


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Alta de usuarios por el administrador. Si no se envía contraseña, se genera una
    temporal que se devuelve UNA sola vez en la respuesta.
    """

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "password")

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def validate_password(self, value):
        if value:
            django_validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", "") or None
        self._generated_password = None
        if password is None:
            password = generate_temporary_password()
            self._generated_password = password
        return User.objects.create_user(
            password=password, must_change_password=True, **validated_data
        )

    def to_representation(self, instance):
        data = UserSerializer(instance).data
        generated = getattr(self, "_generated_password", None)
        if generated:
            data["temporary_password"] = generated
        return data


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")

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
