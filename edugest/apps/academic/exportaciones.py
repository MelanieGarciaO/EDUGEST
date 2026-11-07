"""
Exportación a Excel de los listados del administrador (estudiantes y asignaciones).

Reutiliza la estructura y el exportador de apps.reports para que los archivos tengan el
mismo formato que los reportes (encabezado, filtros aplicados, autofiltro, columnas fijas).
Las importaciones de reports se hacen dentro de las funciones para no acoplar la carga
de la app académica.
"""

from django.utils import timezone

from apps.security.models import User

from .models import Paralelo

CONTENT_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _estado(params, masculino=True):
    valor = params.get("is_active")
    if valor == "true":
        return "Activos" if masculino else "Activas"
    if valor == "false":
        return "Inactivos" if masculino else "Inactivas"
    return "Todos" if masculino else "Todas"


def _paralelo(params):
    pid = params.get("paralelo")
    if pid and pid.isdigit():
        p = Paralelo.objects.select_related("grado").filter(pk=int(pid)).first()
        return p.nombre_completo if p else None
    return None


def _reporte(clave, titulo, descripcion, filtros, seccion, request):
    from apps.reports.datos import Reporte

    return Reporte(
        clave=clave, titulo=titulo, descripcion=descripcion, filtros=filtros,
        secciones=[seccion], generado_por=request.user.full_name, generado_en=timezone.localtime(),
    )


def estudiantes(qs, request):
    from apps.reports.datos import Seccion

    params = request.query_params
    filtros = []
    if paralelo := _paralelo(params):
        filtros.append(("Paralelo", paralelo))
    if busqueda := params.get("search", "").strip():
        filtros.append(("Búsqueda", busqueda))
    filtros.append(("Estado", _estado(params)))

    seccion = Seccion(
        "Estudiantes",
        [("N.º", 0.6), ("Apellidos", 2), ("Nombres", 2), ("Grado", 1.6), ("Paralelo", 1),
         ("Representante", 2.6), ("Correo del representante", 2.8), ("Estado", 1), ("Registrado", 1.2)],
        vacio="No hay estudiantes con los filtros seleccionados.",
    )
    for i, e in enumerate(qs, start=1):
        seccion.filas.append([
            i, e.last_name, e.first_name, e.paralelo.grado.nombre, e.paralelo.nombre,
            e.representante.full_name, e.representante.email,
            "Activo" if e.is_active else "Inactivo", timezone.localtime(e.created_at).date(),
        ])
    return _reporte(
        "estudiantes", "Listado de estudiantes",
        "Estudiantes con su paralelo y representante.", filtros, seccion, request,
    )


def asignaciones(qs, request):
    from apps.reports.datos import Seccion

    params = request.query_params
    filtros = []
    if paralelo := _paralelo(params):
        filtros.append(("Paralelo", paralelo))
    did = params.get("docente")
    if did and did.isdigit() and (docente := User.objects.filter(pk=int(did)).first()):
        filtros.append(("Docente", docente.full_name))
    filtros.append(("Estado", _estado(params, masculino=False)))

    seccion = Seccion(
        "Asignaciones",
        [("N.º", 0.6), ("Grado", 1.6), ("Paralelo", 1), ("Asignatura", 2.2), ("Docente", 2.6),
         ("Correo del docente", 2.8), ("Estudiantes activos", 1.3), ("Estado", 1), ("Creada", 1.2)],
        vacio="No hay asignaciones con los filtros seleccionados.",
    )
    for i, a in enumerate(qs, start=1):
        seccion.filas.append([
            i, a.paralelo.grado.nombre, a.paralelo.nombre, a.asignatura.nombre, a.docente.full_name,
            a.docente.email, a.n_estudiantes, "Activa" if a.is_active else "Inactiva",
            timezone.localtime(a.created_at).date(),
        ])
    return _reporte(
        "asignaciones", "Asignaciones docentes",
        "Qué docente dicta cada asignatura en cada paralelo.", filtros, seccion, request,
    )


def a_xlsx(reporte):
    from apps.reports.exportar import a_xlsx as exportar

    return exportar(reporte)


def nombre_archivo(reporte):
    return f"edugest_{reporte.clave}_{reporte.generado_en:%Y%m%d_%H%M}.xlsx"
