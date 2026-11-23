"""
IP real del cliente.

Detrás del proxy de Render todas las peticiones llegan a Django con REMOTE_ADDR=127.0.0.1;
si los límites se calcularan con esa IP, todos los usuarios compartirían el mismo límite
(5 personas pidiendo un código de recuperación bloquearían a la sexta).

El proxy agrega la IP de quien se conecta AL FINAL de la cabecera X-Forwarded-For y conserva
lo que el cliente haya escrito antes. Por eso se lee de derecha a izquierda y se toma la
primera IP pública: lo que esté a su izquierda lo puede inventar cualquiera.

Con BEHIND_PROXY=False (desarrollo local) se usa REMOTE_ADDR y X-Forwarded-For se ignora.
"""

import ipaddress

from django.conf import settings


def _ip_valida(texto):
    try:
        return ipaddress.ip_address(texto.strip())
    except ValueError:
        return None


def ip_cliente(request):
    """IP del cliente como texto, o None si no se puede determinar."""
    meta = getattr(request, "META", {})
    if not getattr(settings, "BEHIND_PROXY", False):
        ip = _ip_valida(meta.get("REMOTE_ADDR") or "")
        return str(ip) if ip else None

    candidatas = [_ip_valida(parte) for parte in (meta.get("HTTP_X_FORWARDED_FOR") or "").split(",")]
    candidatas = [ip for ip in candidatas if ip]
    for ip in reversed(candidatas):
        if ip.is_global:
            return str(ip)
    # Sin IP pública (p. ej. una prueba desde la red interna): la última que agregó el proxy.
    if candidatas:
        return str(candidatas[-1])
    return None
