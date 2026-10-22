"""
Estado del sistema: modo mantenimiento, chequeo de salud y errores de la API en JSON.

- MaintenanceMiddleware: con MAINTENANCE_MODE=True en el .env, toda la API responde 503
  {"code": "maintenance"} (salvo /api/health/ y el panel de administración de Django).
- api_exception_handler: si la base de datos no responde, la API devuelve 503
  {"code": "service_unavailable"} en lugar de un error 500 genérico.
- ApiErrorMiddleware: cualquier otro error no controlado en /api/ se registra en el log y
  se responde como JSON {"code": "server_error"}, sin exponer detalles internos.
- health: GET /api/health/ responde si el sistema está operativo (lo usa el frontend para
  saber cuándo volvió el servicio).

El frontend usa estos códigos para mostrar la pantalla de mantenimiento o de servicio
caído en lugar de un mensaje de error suelto.
"""

import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.views import exception_handler

logger = logging.getLogger("edugest.sistema")

PREFIJO_API = "/api/"
RUTA_SALUD = "/api/health/"


def datos_mantenimiento():
    """Datos de mantenimiento para el frontend."""
    datos = {
        "code": "maintenance",
        "detail": settings.MAINTENANCE_MESSAGE,
    }
    if settings.MAINTENANCE_UNTIL:
        datos["hasta"] = settings.MAINTENANCE_UNTIL
    return datos


def respuesta_mantenimiento():
    """Respuesta de mantenimiento para el frontend."""
    respuesta = JsonResponse(datos_mantenimiento(), status=503)
    respuesta["Retry-After"] = str(settings.MAINTENANCE_RETRY_SECONDS)
    return respuesta


def respuesta_no_disponible():
    """Respuesta de servicio no disponible para el frontend."""
    respuesta = JsonResponse(
        {
            "code": "service_unavailable",
            "detail": "El servicio no está disponible en este momento. Inténtalo de nuevo en unos minutos.",
        },
        status=503,
    )
    respuesta["Retry-After"] = "30"
    return respuesta


class MaintenanceMiddleware:
    """Corta la API con 503 mientras MAINTENANCE_MODE esté activo."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.MAINTENANCE_MODE
            and request.path.startswith(PREFIJO_API)
            and request.path != RUTA_SALUD
            and request.method != "OPTIONS"  # el preflight de CORS debe pasar
        ):
            return respuesta_mantenimiento()
        return self.get_response(request)


class ApiErrorMiddleware:
    """Errores no controlados de la API: se registran y se responden en JSON."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if not request.path.startswith(PREFIJO_API):
            return None
        if isinstance(exception, DatabaseError):
            logger.error("Base de datos no disponible en %s", request.path, exc_info=exception)
            return respuesta_no_disponible()
        logger.error("Error no controlado en %s", request.path, exc_info=exception)
        return JsonResponse(
            {
                "code": "server_error",
                "detail": "Ocurrió un error inesperado en el servidor. Ya quedó registrado.",
            },
            status=500,
        )


def api_exception_handler(exc, context):
    """Manejador de DRF: la base de datos caída se informa como 503, no como 500."""
    if isinstance(exc, DatabaseError):
        logger.error("Base de datos no disponible", exc_info=exc)
        return respuesta_no_disponible()
    return exception_handler(exc, context)


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    """Estado del sistema. 200 si funciona; 503 si está en mantenimiento o sin base de datos."""
    if settings.MAINTENANCE_MODE:
        return respuesta_mantenimiento()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.error("Chequeo de salud: la base de datos no responde")
        return respuesta_no_disponible()
    return JsonResponse({"status": "ok"})
