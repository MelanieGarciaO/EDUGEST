from apps.security.models import Role
from apps.security.permissions import RolePermission


class IsDocenteOrRepresentante(RolePermission):
    allowed_roles = (
        Role.DOCENTE, 
        Role.REPRESENTANTE
    )
