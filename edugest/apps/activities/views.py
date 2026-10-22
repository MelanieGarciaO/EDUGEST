from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.academic import selectors as academic_selectors
from apps.academic.models import AsignacionDocente
from apps.grades.models import Calificacion
from apps.security.models import Role
from apps.security.permissions import IsDocente, IsPasswordUpToDate

from . import nlp, clock, selectors
from .models import Actividad, Extraccion
from .serializers import (
    ActividadCrearSerializer,
    ActividadEditarSerializer,
    ActividadSerializer,
    PrevisualizarSerializer,
)
from .signals import actividad_cancelada


def _id_param(params, nombre):
    valor = params.get(nombre)
    if not valor:
        return None
    if not valor.isdigit():
        raise ValidationError({nombre: "Debe ser un número."})
    return int(valor)


class ActividadViewSet(viewsets.ModelViewSet):
    """
    Actividades académicas.

    - Lectura (cualquier rol, ya restringida por rol): listado y detalle.
        Filtros: ?paralelo= ?asignatura= ?estudiante= ?vigencia=pendiente|finalizada|cancelada
                 ?search=texto
    - Escritura (solo docentes sobre sus propias asignaciones):
        POST   previsualizar/  -> procesa la indicación con PLN y devuelve una propuesta
        POST   /               -> publica la actividad (tras revisar la propuesta)
        PATCH  /{id}/          -> edita descripción, fecha, materiales o tema
        POST   /{id}/cancelar/ -> cancela la actividad
    No hay borrado.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsPasswordUpToDate()]
        return [IsDocente()]

    def get_serializer_class(self):
        if self.action == "create":
            return ActividadCrearSerializer
        if self.action in ("update", "partial_update"):
            return ActividadEditarSerializer
        if self.action == "previsualizar":
            return PrevisualizarSerializer
        return ActividadSerializer

    def get_queryset(self):
        user = self.request.user
        params = self.request.query_params
        hoy, hora = timezone.localdate(), clock.hora_actual()
        qs = selectors.actividades_visibles(user)

        paralelo = _id_param(params, "paralelo")
        if paralelo is not None:
            qs = qs.filter(asignacion__paralelo_id=paralelo)

        asignatura = _id_param(params, "asignatura")
        if asignatura is not None:
            qs = qs.filter(asignacion__asignatura_id=asignatura)

        estudiante = _id_param(params, "estudiante")
        if estudiante is not None:
            if academic_selectors.puede_ver_estudiante(user, estudiante):
                qs = qs.filter(asignacion__paralelo__estudiantes__id=estudiante).distinct()
            else:
                qs = qs.none()

        search = params.get("search")
        if search:
            qs = qs.filter(descripcion__icontains=search)

        vigencia = params.get("vigencia")
        orden = ("fecha_entrega", "hora_entrega", "id")
        if vigencia:
            if vigencia == "pendiente":
                qs = qs.pendientes(hoy, hora)
            elif vigencia == "finalizada":
                qs = qs.finalizadas(hoy, hora)
                orden = ("-fecha_entrega", "-hora_entrega", "-id")
            elif vigencia == "cancelada":
                qs = qs.canceladas()
            else:
                raise ValidationError(
                    {"vigencia": "Valores válidos: pendiente, finalizada, cancelada."}
                )
        if user.role == Role.REPRESENTANTE:
            qs = qs.prefetch_related(self._prefetch_notas(user, estudiante))
        return qs.order_by(*orden)

    @staticmethod
    def _prefetch_notas(user, estudiante=None):
        """Notas de los estudiantes del representante (y del filtrado, si hay) por actividad."""
        notas = Calificacion.objects.filter(
            estudiante__representante=user, estudiante__is_active=True
        ).select_related("estudiante", "tema").order_by("estudiante__last_name", "estudiante__first_name")
        if estudiante is not None:
            notas = notas.filter(estudiante_id=estudiante)
        return Prefetch("calificaciones", queryset=notas, to_attr="notas_representante")

    # --- Vista previa con PLN -------------------------------------------------
    @action(detail=False, methods=["post"], url_path="previsualizar")
    def previsualizar(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paralelo = serializer.validated_data["paralelo"]
        texto = serializer.validated_data["texto"]

        asignaciones = AsignacionDocente.objects.filter(
            docente=request.user, paralelo=paralelo, is_active=True
        ).select_related("asignatura")
        disponibles = [(a.asignatura_id, a.asignatura.nombre) for a in asignaciones]

        pipeline = nlp.obtener_nlp()
        propuesta = nlp.extraer(texto, disponibles, timezone.localdate(), nlp=pipeline)

        extraccion = Extraccion.objects.create(
            docente=request.user,
            paralelo=paralelo,
            texto_original=texto,
            resultado=propuesta,
            motor=propuesta["motor"],
        )
        return Response(
            {
                "extraccion": extraccion.id,
                "paralelo": paralelo.id,
                "propuesta": propuesta,
                "asignaturas_disponibles": [
                    {"id": asig_id, "nombre": nombre} for asig_id, nombre in disponibles
                ],
            }
        )

    # --- Cancelación ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="cancelar")
    def cancelar(self, request, pk=None):
        actividad = self.get_object()
        if actividad.estado == Actividad.Estado.CANCELADA:
            return Response(
                {"detail": "La actividad ya está cancelada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        actividad.estado = Actividad.Estado.CANCELADA
        actividad.cancelada_en = timezone.now()
        actividad.save(update_fields=["estado", "cancelada_en", "updated_at"])
        transaction.on_commit(
            lambda: actividad_cancelada.send(sender=Actividad, actividad=actividad)
        )
        return Response(ActividadSerializer(actividad, context={"request": request}).data)
