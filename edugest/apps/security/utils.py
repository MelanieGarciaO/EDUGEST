import secrets

from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)

# Sin caracteres ambiguos (0/O, 1/l/I) para facilitar su entrega al usuario.
_LOWER = "abcdefghijkmnpqrstuvwxyz"
_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_DIGITS = "23456789"


def generate_temporary_password(length=12):
    """Genera una contraseña temporal aleatoria con minúsculas, mayúsculas y dígitos."""
    alphabet = _LOWER + _UPPER + _DIGITS
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c in _LOWER for c in password)
            and any(c in _UPPER for c in password)
            and any(c in _DIGITS for c in password)
        ):
            return password


def revoke_user_tokens(user):
    """Invalida todos los refresh tokens vigentes del usuario (cierra sus sesiones)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
