from django.conf import settings
from django.db.models import Exists, OuterRef, Q, Subquery
from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from . import avisos, cola_accesos, exportaciones, importaciones, recuperacion
from .models import EnvioAcceso, Role, User
from .permissions import IsAdministrador
from .red import ip_cliente
from .throttles import LoginPorIP
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
    """
    POST: correo + contraseña -> access, refresh y datos del usuario.

    Dos límites: 5 intentos por minuto desde la misma IP (LoginPorIP) y LOGIN_FALLOS_MAX
    intentos FALLIDOS por cuenta (recuperacion.intentos_login), que frena a quien prueba
    contraseñas de una cuenta cambiando de IP.
    """

    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [LoginPorIP]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        email = request.data.get("email") if hasattr(request.data, "get") else None
        recuperacion.comprobar_bloqueo_login(email)
        try:
            respuesta = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            recuperacion.registrar_fallo_login(email)
            raise
        recuperacion.limpiar_fallos_login(email)
        return respuesta


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
        en_cola = EnvioAcceso.objects.filter(
            usuario=OuterRef("pk"), estado__in=(EnvioAcceso.Estado.PENDIENTE, EnvioAcceso.Estado.ENVIANDO)
        )
        qs = User.objects.annotate(estado_correo_acceso=Subquery(ultimo_correo), envio_en_cola=Exists(en_cola))
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

    def list(self, request, *args, **kwargs):
        # Si quedaron correos en cola (p. ej. el servidor se reinició), se retoman al abrir la lista.
        cola_accesos.despertar_si_hay_pendientes()
        return super().list(request, *args, **kwargs)

    # --- Importación y exportación con Excel ------------------------------------
    @action(detail=False, methods=["get"])
    def plantilla(self, request):
        """GET users/plantilla/ — Excel con las columnas y la lista de roles."""
        respuesta = HttpResponse(importaciones.generar_plantilla(), content_type=importaciones.CONTENT_TYPE)
        respuesta["Content-Disposition"] = 'attachment; filename="plantilla_usuarios.xlsx"'
        respuesta["Cache-Control"] = "no-store"
        return respuesta

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def importar(self, request):
        """
        POST users/importar/ (multipart: archivo, confirmar=true|false)
        Sin confirmar: vista previa. Confirmando: registra todo o nada y pone en cola el correo
        con la contraseña temporal de cada usuario (se envían en segundo plano).
        """
        confirmar = str(request.data.get("confirmar", "")).lower() == "true"
        resultado = importaciones.importar(request.FILES.get("archivo"), confirmar)
        if confirmar and resultado["errores"]:
            return Response(
                {"archivo": [importaciones.MENSAJE_CON_ERRORES], "vista_previa": resultado},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(resultado)

    @action(detail=False, methods=["get"])
    def exportar(self, request):
        """GET users/exportar/ — Excel con el listado, aplicando los mismos filtros de la pantalla."""
        reporte = exportaciones.usuarios(self.get_queryset(), request)
        respuesta = HttpResponse(exportaciones.a_xlsx(reporte), content_type=exportaciones.CONTENT_TYPE_XLSX)
        respuesta["Content-Disposition"] = f'attachment; filename="{exportaciones.nombre_archivo(reporte)}"'
        respuesta["Cache-Control"] = "no-store"
        return respuesta

    @action(detail=False, methods=["get"], url_path="cola-accesos")
    def cola_accesos_estado(self, request):
        """GET users/cola-accesos/?lote=… — avance del envío de correos de una importación."""
        lote = request.query_params.get("lote", "")
        conteo = cola_accesos.resumen_lote(lote) if lote else {}
        return Response({"lote": lote, **conteo})

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
        cola_accesos.cancelar_pendientes(user)  # si estaba en cola por una importación
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
    return ip_cliente(request)  # IP real aunque la app esté detrás del proxy de Render


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
