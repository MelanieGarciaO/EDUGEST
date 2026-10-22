from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from apps.security.permissions import IsAdministrador, IsPasswordUpToDate

from . import selectors
from .grados import grado_maximo
from .models import Asignatura, AsignacionDocente, Estudiante, Grado, Tema
from .serializers import (
    AsignaturaSerializer,
    AsignacionDocenteSerializer,
    EstudianteSerializer,
    GradoSerializer,
    ParaleloSerializer,
    TemaSerializer,
)


def filter_by_id(qs, params, name, lookup):
    """Filtra por un parámetro numérico de la URL; responde 400 si no es un número."""
    value = params.get(name)
    if value:
        if not value.isdigit():
            raise ValidationError({name: "Debe ser un número."})
        qs = qs.filter(**{lookup: int(value)})
    return qs


def filter_by_active(qs, params):
    value = params.get("is_active")
    if value in ("true", "false"):
        qs = qs.filter(is_active=(value == "true"))
    return qs


class AcademicViewSet(viewsets.ModelViewSet):
    """
    Base: la lectura está abierta a cualquier rol (con la información ya restringida por
    `get_queryset`) y la escritura es exclusiva del administrador. No hay borrado: los
    registros se desactivan con PATCH {"is_active": false}.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsPasswordUpToDate()]
        return [IsAdministrador()]


class GradoViewSet(AcademicViewSet):
    serializer_class = GradoSerializer

    def get_queryset(self):
        # Solo se ofrecen los grados habilitados (ver grados.py).
        return Grado.objects.filter(orden__lte=grado_maximo())


class AsignaturaViewSet(AcademicViewSet):
    serializer_class = AsignaturaSerializer

    def get_queryset(self):
        qs = Asignatura.objects.all()
        qs = filter_by_active(qs, self.request.query_params)
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(nombre__icontains=search)
        return qs.order_by("nombre")


class ParaleloViewSet(AcademicViewSet):
    serializer_class = ParaleloSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = selectors.paralelos_visibles(self.request.user)
        qs = filter_by_id(qs, params, "grado", "grado_id")
        qs = filter_by_active(qs, params)
        return qs.order_by("grado__orden", "nombre")


class EstudianteViewSet(AcademicViewSet):
    serializer_class = EstudianteSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = selectors.estudiantes_visibles(self.request.user)
        qs = filter_by_id(qs, params, "paralelo", "paralelo_id")
        qs = filter_by_id(qs, params, "grado", "paralelo__grado_id")
        qs = filter_by_active(qs, params)
        search = params.get("search")
        if search:
            qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        return qs.order_by("last_name", "first_name")


class AsignacionDocenteViewSet(AcademicViewSet):
    serializer_class = AsignacionDocenteSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = selectors.asignaciones_visibles(self.request.user)
        qs = filter_by_id(qs, params, "docente", "docente_id")
        qs = filter_by_id(qs, params, "paralelo", "paralelo_id")
        qs = filter_by_id(qs, params, "asignatura", "asignatura_id")
        qs = filter_by_active(qs, params)
        return qs.order_by("paralelo__grado__orden", "paralelo__nombre", "asignatura__nombre")


class TemaViewSet(AcademicViewSet):
    """
    Catálogo de temas y subtemas. Lectura para cualquier rol; escritura solo del
    administrador. Filtros: ?grado= ?asignatura= ?padre=<id>|null ?is_active= ?search=
    """

    serializer_class = TemaSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Tema.objects.select_related("grado", "asignatura", "padre")
        qs = filter_by_id(qs, params, "grado", "grado_id")
        qs = filter_by_id(qs, params, "asignatura", "asignatura_id")
        padre = params.get("padre")
        if padre == "null":
            qs = qs.filter(padre__isnull=True)
        else:
            qs = filter_by_id(qs, params, "padre", "padre_id")
        qs = filter_by_active(qs, params)
        search = params.get("search")
        if search:
            qs = qs.filter(nombre__icontains=search)
        return qs.order_by("grado__orden", "asignatura__nombre", "nombre")
