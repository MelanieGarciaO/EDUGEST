"""
Límites de peticiones de DRF identificando al cliente por su IP real (ver red.py).

Los de DRF usan toda la cabecera X-Forwarded-For como identificador: cambiándola en cada
petición se saltaba el límite de 5 intentos de inicio de sesión por minuto. Y sin la cabecera,
detrás de Render, todos los visitantes compartían el mismo límite (REMOTE_ADDR=127.0.0.1).
"""

from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle

from .red import ip_cliente


class _PorIPReal:
    def get_ident(self, request):
        return ip_cliente(request) or "ip-desconocida"


class AnonPorIP(_PorIPReal, AnonRateThrottle):
    """Visitantes sin sesión: 60 por minuto por IP."""


class UsuarioPorIP(_PorIPReal, UserRateThrottle):
    """Con sesión: 300 por minuto por usuario (sin sesión, por IP)."""


class LoginPorIP(_PorIPReal, ScopedRateThrottle):
    """Vistas con throttle_scope (inicio de sesión: 5 por minuto por IP)."""
