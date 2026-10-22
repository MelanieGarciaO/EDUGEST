from rest_framework.permissions import BasePermission

from .models import Role

PASSWORD_CHANGE_MESSAGE = "Debes cambiar tu contraseña temporal antes de continuar."


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
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and not user.must_change_password
        )
