from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Role, User
from .permissions import IsAdministrador
from .serializers import (
    AceptarTerminosSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .utils import generate_temporary_password, revoke_user_tokens


class LoginView(TokenObtainPairView):
    """POST: correo + contraseña -> access, refresh y datos del usuario."""

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    """POST: invalida el refresh token enviado."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET: datos del usuario autenticado (disponible incluso con contraseña temporal)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LegalInfoView(APIView):
    """GET (público): datos que muestran la política de privacidad y los términos de uso."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(
            {
                "version": settings.LEGAL_VERSION,
                "vigente_desde": settings.LEGAL_VIGENTE_DESDE,
                "institucion": settings.INSTITUCION_NOMBRE,
                "ciudad": settings.INSTITUCION_CIUDAD,
                "correo_privacidad": settings.INSTITUCION_CORREO_PRIVACIDAD,
                "plazo_conservacion": settings.DATOS_PLAZO_CONSERVACION,
            }
        )


class AceptarTerminosView(APIView):
    """POST: registra que el usuario aceptó la versión vigente de términos y privacidad."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AceptarTerminosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.terminos_version = serializer.validated_data["version"]
        user.terminos_aceptados_en = timezone.now()
        user.save(update_fields=["terminos_version", "terminos_aceptados_en", "updated_at"])
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    """POST: cambia la contraseña, cierra las demás sesiones y entrega tokens nuevos."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])

        revoke_user_tokens(user)
        refresh = LoginSerializer.get_token(user)
        return Response(
            {
                "detail": "Contraseña actualizada correctamente.",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            }
        )


class UserViewSet(viewsets.ModelViewSet):
    """
    Gestión de usuarios (solo administrador). No se eliminan registros: se
    desactivan, para conservar la trazabilidad.

    Filtros opcionales: ?role=DOCENTE  ?is_active=true  ?search=texto
    """

    permission_classes = [IsAdministrador]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = User.objects.all()
        params = self.request.query_params

        role = params.get("role")
        if role in Role.values:
            qs = qs.filter(role=role)

        is_active = params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=(is_active == "true"))

        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return qs.order_by("last_name", "first_name")

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        return UserSerializer

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {"detail": "No puedes desactivar tu propia cuenta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        revoke_user_tokens(user)
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        user = self.get_object()
        if user == request.user:
            return Response(
                {"detail": "Para tu propia cuenta usa el cambio de contraseña."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        temporary_password = generate_temporary_password()
        user.set_password(temporary_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        revoke_user_tokens(user)
        return Response(
            {
                "detail": "Contraseña temporal generada. Entrégala al usuario; no se volverá a mostrar.",
                "temporary_password": temporary_password,
            }
        )
