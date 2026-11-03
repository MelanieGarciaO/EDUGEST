from django.db import transaction
from django.db.models import Prefetch
from django.http import FileResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.academic import selectors as academic_selectors
from apps.academic.models import AsignacionDocente, Tema
from apps.grades.models import Calificacion
from apps.security.models import Role
from apps.security.permissions import IsDocente, IsPasswordUpToDate, IsRepresentante

from . import clock, entregas, nlp, selectors
from .models import Actividad, AdjuntoActividad, ArchivoEntrega, Extraccion
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
        POST   /{id}/adjuntos/ -> adjunta un PDF (multipart «archivo»)
    - Entregas desde la app:
        GET    /{id}/entregas/ -> estado por estudiante (docente: todos; representante: los suyos)
        POST   /{id}/entregas/ -> el representante sube una foto o PDF
                                  (multipart «archivo», «estudiante», «comentario» opcional)
    No hay borrado de actividades.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    parser_classes = [JSONParser, MultiPartParser]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsPasswordUpToDate()]
        if self.action == "entregas":
            return [IsRepresentante()] if self.request.method == "POST" else [IsPasswordUpToDate()]
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

        # Catálogo de temas (y subtemas) del grado para reconocer el tema en la indicación.
        temas = list(
            Tema.objects.filter(
                grado_id=paralelo.grado_id,
                asignatura_id__in=[asig_id for asig_id, _ in disponibles],
                is_active=True,
            ).values_list("id", "nombre", "asignatura_id")
        )

        pipeline = nlp.obtener_nlp()
        propuesta = nlp.extraer(
            texto, disponibles, timezone.localdate(), nlp=pipeline, temas=temas
        )

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
    # --- Archivos ---------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def adjuntos(self, request, pk=None):
        entregas.subir_adjunto(self.get_object(), request.user, request.FILES.get("archivo"))
        actividad = self.get_queryset().get(pk=pk)
        return Response(
            ActividadSerializer(actividad, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"])
    def entregas(self, request, pk=None):
        actividad = self.get_object()
        if request.method == "POST":
            entregas.subir_entrega(
                actividad,
                request.user,
                request.data.get("estudiante"),
                request.FILES.get("archivo"),
                request.data.get("comentario", ""),
            )
            return Response(entregas.entregas_de(actividad, request.user), status=status.HTTP_201_CREATED)
        return Response(entregas.entregas_de(actividad, request.user))

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


def _respuesta_archivo(registro, content_type):
    respuesta = FileResponse(
        registro.archivo.open("rb"), content_type=content_type, filename=registro.nombre
    )
    respuesta["Content-Disposition"] = respuesta["Content-Disposition"].replace("attachment", "inline")
    respuesta["Cache-Control"] = "private, max-age=300"
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


class AdjuntoViewSet(viewsets.GenericViewSet):
    """
    PDF adjuntos por el docente.
      GET    /{id}/archivo/  quien puede ver la actividad (docente, representantes, admin)
      DELETE /{id}/          el docente de la actividad
    """

    def get_permissions(self):
        return [IsDocente()] if self.action == "destroy" else [IsPasswordUpToDate()]

    def get_queryset(self):
        return AdjuntoActividad.objects.filter(
            actividad__in=selectors.actividades_visibles(self.request.user)
        ).select_related("actividad__asignacion")

    def destroy(self, request, pk=None):
        entregas.eliminar_adjunto(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        return _respuesta_archivo(self.get_object(), "application/pdf")


class ArchivoEntregaViewSet(viewsets.GenericViewSet):
    """
    Archivos de las entregas desde la app.
      GET    /{id}/archivo/  docente de la actividad, administrador o representante del estudiante
      DELETE /{id}/          quien lo subió, mientras no haya nota
    """

    def get_permissions(self):
        return [IsRepresentante()] if self.action == "destroy" else [IsPasswordUpToDate()]

    def get_queryset(self):
        user = self.request.user
        qs = ArchivoEntrega.objects.filter(
            actividad__in=selectors.actividades_visibles(user)
        ).select_related("actividad__asignacion")
        if user.role == Role.REPRESENTANTE:
            qs = qs.filter(estudiante__representante=user)
        return qs

    def destroy(self, request, pk=None):
        entregas.eliminar_archivo_entrega(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        registro = self.get_object()
        tipo = "application/pdf" if registro.tipo == ArchivoEntrega.Tipo.PDF else "image/jpeg"
        return _respuesta_archivo(registro, tipo)
