from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Role

PASSWORD_CHANGE_MESSAGE = "Debes cambiar tu contraseña temporal antes de continuar."
TERMINOS_MESSAGE = "Debes aceptar los términos de uso y la política de privacidad vigentes para continuar."


def exigir_terminos(user):
    """
    403 con code «terminos_pendientes» si el usuario no aceptó la versión vigente. El frontend
    ya lo lleva a /aceptar-terminos; esto cubre a quien llame a la API directamente o a quien
    tenía la sesión abierta cuando cambió LEGAL_VERSION (el frontend lo redirige al recibirlo).
    """
    if getattr(settings, "TERMINOS_OBLIGATORIOS_API", True) and user.terminos_version != settings.LEGAL_VERSION:
        raise PermissionDenied({"detail": TERMINOS_MESSAGE, "code": "terminos_pendientes"})


class RolePermission(BasePermission):
    """
    Base para permisos por rol. Exige usuario autenticado, activo, con la contraseña
    temporal ya cambiada y con alguno de los roles de `allowed_roles`.
    """

    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        if user.must_change_password:
            self.message = PASSWORD_CHANGE_MESSAGE
            return False
        exigir_terminos(user)
        return user.role in self.allowed_roles


class IsAdministrador(RolePermission):
    allowed_roles = (Role.ADMINISTRADOR,)


class IsDocente(RolePermission):
    allowed_roles = (Role.DOCENTE,)


class IsRepresentante(RolePermission):
    allowed_roles = (Role.REPRESENTANTE,)


class IsDocenteOrAdministrador(RolePermission):
    allowed_roles = (Role.DOCENTE, Role.ADMINISTRADOR)


class IsPasswordUpToDate(BasePermission):
    """Cualquier usuario autenticado que ya no tenga una contraseña temporal."""

    message = PASSWORD_CHANGE_MESSAGE

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_active and not user.must_change_password):
            return False
        exigir_terminos(user)
        return True
