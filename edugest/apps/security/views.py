from django.conf import settings
from django.db.models import OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import avisos, recuperacion
from .models import Role, User
from .permissions import IsAdministrador
from .serializers import (
    AceptarTerminosSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RestablecerSerializer,
    TIPOS_CORREO_ACCESO,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .utils import revoke_user_tokens


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


def _sesion_nueva(user, detalle):
    """Tokens nuevos tras cambiar la contraseña (las demás sesiones ya se cerraron)."""
    refresh = LoginSerializer.get_token(user)
    return Response(
        {
            "detail": detalle,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        }
    )


class ChangePasswordView(APIView):
    """
    POST {clave_temporal, new_password}: crea la contraseña nueva con la clave temporal que
    llegó por correo (primer acceso, cuenta recuperada o la pedida desde el Perfil).
    Cierra las demás sesiones y entrega tokens nuevos.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        user = recuperacion.cambiar_clave(request.user, datos["clave_temporal"], datos["new_password"])
        return _sesion_nueva(user, "Contraseña actualizada correctamente.")


class ClaveTemporalView(APIView):
    """POST: envía al correo del usuario una clave temporal para cambiar la contraseña desde el Perfil."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        minutos = recuperacion.solicitar_clave_perfil(request.user, _ip(request))
        return Response({
            "detail": f"Te enviamos una clave temporal a {request.user.email}. Vence en {minutos} minutos.",
            "minutos": minutos,
        })


class UserViewSet(viewsets.ModelViewSet):
    """
    Gestión de usuarios (solo administrador). No se eliminan registros: se
    desactivan, para conservar la trazabilidad.

    Filtros opcionales: ?role=DOCENTE  ?is_active=true  ?search=texto
    """

    permission_classes = [IsAdministrador]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        from apps.notifications.models import Notificacion

        ultimo_correo = (
            Notificacion.objects.filter(usuario=OuterRef("pk"), tipo__in=TIPOS_CORREO_ACCESO)
            .order_by("-created_at", "-id").values("estado_correo")[:1]
        )
        qs = User.objects.annotate(estado_correo_acceso=Subquery(ultimo_correo))
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

    @action(detail=True, methods=["post"], url_path="reenviar-acceso")
    def reenviar_acceso(self, request, pk=None):
        """
        Reenvía el correo de bienvenida con una contraseña temporal NUEVA, solo a cuentas que
        aún no se han activado (por ejemplo, si el primer correo no llegó). El administrador
        no ve la contraseña. Si el usuario ya ingresó alguna vez, debe usar «¿Olvidaste tu contraseña?».
        """
        user = self.get_object()
        if not user.is_active:
            return Response({"detail": "Activa la cuenta antes de reenviar el acceso."}, status=status.HTTP_400_BAD_REQUEST)
        if not (user.must_change_password and user.last_login is None):
            return Response(
                {"detail": "Este usuario ya activó su cuenta. Si olvidó su contraseña, puede recuperarla "
                           "con «¿Olvidaste tu contraseña?» en la pantalla de inicio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recuperacion.asignar_clave_bienvenida(user, motivo=avisos.REENVIADA)  # nuevo plazo de 2 horas
        datos = UserSerializer(self.get_queryset().get(pk=user.pk)).data
        if datos["correo_acceso"] == "ERROR":
            return Response(
                {**datos, "detail": f"No se pudo enviar el correo a {user.email}. Revisa la dirección o el servicio de correo."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({**datos, "detail": f"Se envió un nuevo correo de acceso a {user.email}."})


# ---------------------------------------------------------------------------
# Recuperación de contraseña con código OTP (público, sin sesión)
# ---------------------------------------------------------------------------
def _ip(request):
    return request.META.get("REMOTE_ADDR") or None


class RecuperarSolicitarView(APIView):
    """POST {email}: envía un código de 6 dígitos si la cuenta existe (respuesta idéntica si no)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        recuperacion.solicitar(request.data.get("email"), _ip(request))
        return Response({"detail": recuperacion.MENSAJE_SOLICITUD})


class RecuperarVerificarView(APIView):
    """POST {email, codigo}: si el código es válido, devuelve una contraseña temporal (una sola vez)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        temporal = recuperacion.verificar(request.data.get("email"), request.data.get("codigo"), _ip(request))
        return Response({
            "detail": "Código verificado. Usa esta contraseña temporal para crear tu contraseña nueva.",
            "temporary_password": temporal,
        })


class RecuperarRestablecerView(APIView):
    """POST {email, clave_temporal, new_password}: crea la contraseña nueva en el recuperador e inicia sesión."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RestablecerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        user = recuperacion.restablecer(d["email"], d["clave_temporal"], d["new_password"], _ip(request))
        return _sesion_nueva(user, "Tu contraseña nueva quedó guardada.")
