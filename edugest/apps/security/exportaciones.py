"""
Exportación a Excel del listado de usuarios (solo administrador). Respeta los filtros de la
pantalla (búsqueda, rol, estado) y usa el mismo formato que los demás reportes.
Nunca incluye contraseñas ni claves temporales.
"""

from django.utils import timezone

from apps.academic.exportaciones import CONTENT_TYPE_XLSX, a_xlsx, nombre_archivo

from .models import Role

__all__ = ["CONTENT_TYPE_XLSX", "a_xlsx", "nombre_archivo", "usuarios"]

ESTADO_CORREO = {
    "EN_COLA": "Correo en cola",
    "PENDIENTE": "Correo en cola",
    "ENVIADO": "Correo enviado",
    "ERROR": "Correo no enviado",
}


def _cuenta(u):
    if not u.is_active:
        return "Desactivada"
    if u.must_change_password and u.last_login is None:
        estado = "EN_COLA" if getattr(u, "envio_en_cola", False) else getattr(u, "estado_correo_acceso", None)
        return f"Sin activar ({ESTADO_CORREO.get(estado, 'sin registro de correo')})"
    if u.must_change_password:
        return "Debe crear su contraseña"
    return "Activa"


def _fecha(valor):
    return timezone.localtime(valor).replace(tzinfo=None) if valor else ""


def usuarios(qs, request):
    from apps.reports.datos import Reporte, Seccion

    params = request.query_params
    filtros = []
    if params.get("role") in Role.values:
        filtros.append(("Rol", Role(params["role"]).label))
    if busqueda := params.get("search", "").strip():
        filtros.append(("Búsqueda", busqueda))
    filtros.append(("Estado", {"true": "Activos", "false": "Inactivos"}.get(params.get("is_active"), "Todos")))

    seccion = Seccion(
        "Usuarios",
        [("N.º", 0.6), ("Apellidos", 2), ("Nombres", 2), ("Correo", 3), ("Rol", 1.4), ("Estado", 1),
         ("Cuenta", 2.6), ("Último ingreso", 1.6), ("Registrado", 1.4)],
        vacio="No hay usuarios con los filtros seleccionados.",
    )
    for i, u in enumerate(qs, start=1):
        seccion.filas.append([
            i, u.last_name, u.first_name, u.email, u.get_role_display(),
            "Activo" if u.is_active else "Inactivo", _cuenta(u), _fecha(u.last_login),
            timezone.localtime(u.date_joined).date(),
        ])
    return Reporte(
        clave="usuarios", titulo="Listado de usuarios",
        descripcion="Usuarios registrados en EduGest con su rol y el estado de su cuenta.",
        filtros=filtros, secciones=[seccion], generado_por=request.user.full_name,
        generado_en=timezone.localtime(),
    )
