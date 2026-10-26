from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.views import APIView

from apps.academic import selectors as academic_selectors
from apps.academic.views import filter_by_active, filter_by_id
from apps.security.models import Role
from apps.security.permissions import (
    IsAdministrador,
    IsDocente,
    IsDocenteOrAdministrador,
    IsPasswordUpToDate,
    IsRepresentante,
)

from . import alerta, evidencias, selectors, services
from .models import ActividadRefuerzo, EstrategiaRefuerzo, NivelActividad, PlanRefuerzo
from .permissions import IsDocenteOrRepresentante
from .serializers import (
    EvidenciaSerializer,
    ActividadRefuerzoEditarSerializer,
    ActividadRefuerzoSerializer,
    AgregarActividadSerializer,
    GenerarPlanSerializer,
    PlanSerializer,
    RecursoSerializer,
    TemaPlanEditarSerializer,
    TemaPlanSerializer,
)


class RecursoViewSet(viewsets.ModelViewSet):
    """
    Banco de recursos de refuerzo (docentes en sus asignaturas y grados, y administrador).
    Todos los docentes de una asignatura y grado ven el banco completo, pero solo el autor
    (o el administrador) edita un recurso. No hay borrado: se desactiva con is_active.
    Filtros: ?tema= ?asignatura= ?grado= ?nivel= ?estrategia= ?is_active= ?search=
    """

    serializer_class = RecursoSerializer
    permission_classes = [IsDocenteOrAdministrador]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        params = self.request.query_params
        qs = selectors.recursos_visibles(self.request.user)
        qs = filter_by_id(qs, params, "tema", "tema_id")
        qs = filter_by_id(qs, params, "asignatura", "tema__asignatura_id")
        qs = filter_by_id(qs, params, "grado", "tema__grado_id")
        qs = filter_by_active(qs, params)
        nivel = params.get("nivel")
        if nivel:
            nivel = nivel.upper()
            if nivel not in NivelActividad.values:
                raise ValidationError({"nivel": "Valores válidos: BASICO, INTERMEDIO, AVANZADO."})
            qs = qs.filter(nivel=nivel)
        estrategia = params.get("estrategia")
        if estrategia:
            estrategia = estrategia.upper()
            if estrategia not in EstrategiaRefuerzo.values:
                raise ValidationError({"estrategia": f"Valores válidos: {', '.join(EstrategiaRefuerzo.values)}."})
            qs = qs.filter(estrategia=estrategia)
        search = params.get("search")
        if search:
            qs = qs.filter(Q(titulo__icontains=search) | Q(instrucciones__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    def perform_update(self, serializer):
        user = self.request.user
        if user.role == Role.DOCENTE and serializer.instance.creado_por_id != user.id:
            raise PermissionDenied("Solo el autor del recurso (o el administrador) puede editarlo.")
        serializer.save()


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Planes de refuerzo.

    Lectura (según rol). Filtros: ?estudiante= ?asignatura= ?paralelo= ?estado=
                                  ?evaluacion=pendiente|evaluado (planes completados)
    Acciones del docente:
      POST generar/       {"estudiante": id, "asignatura": id,
                           "temas_manuales": [{"tema": id, "motivo": "..."}]  (opcional)}
                          -> propuesta de plan
      POST /{id}/aprobar/                                      -> publica el plan a la familia
      POST /{id}/cancelar/
    Acción del representante:
      POST /{id}/revisar/                                      -> acuse de recibo del plan
    """

    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ("generar", "aprobar", "cancelar"):
            return [IsDocente()]
        if self.action == "revisar":
            return [IsRepresentante()]
        return [IsPasswordUpToDate()]

    def get_queryset(self):
        params = self.request.query_params
        qs = selectors.planes_visibles(self.request.user)
        qs = filter_by_id(qs, params, "estudiante", "estudiante_id")
        qs = filter_by_id(qs, params, "asignatura", "asignatura_id")
        qs = filter_by_id(qs, params, "paralelo", "estudiante__paralelo_id")
        estado = params.get("estado")
        if estado:
            estado = estado.upper()
            if estado not in PlanRefuerzo.Estado.values:
                raise ValidationError(
                    {"estado": "Valores válidos: PROPUESTA, APROBADA, COMPLETADA, CANCELADA."}
                )
            qs = qs.filter(estado=estado)
        evaluacion = params.get("evaluacion")
        if evaluacion:
            evaluacion = evaluacion.lower()
            if evaluacion == "pendiente":
                # Completados con al menos un tema sin evaluar.
                qs = qs.filter(estado=PlanRefuerzo.Estado.COMPLETADA, temas__superado__isnull=True)
            elif evaluacion == "evaluado":
                qs = qs.filter(estado=PlanRefuerzo.Estado.COMPLETADA).exclude(
                    temas__superado__isnull=True
                )
            else:
                raise ValidationError({"evaluacion": "Valores válidos: pendiente, evaluado."})
            qs = qs.distinct()
        return qs.order_by("-created_at", "-id")

    def _responder(self, request, plan_id, codigo=status.HTTP_200_OK):
        plan = selectors.planes_visibles(request.user).get(pk=plan_id)
        return Response(PlanSerializer(plan, context={"request": request}).data, status=codigo)

    @action(detail=False, methods=["post"])
    def generar(self, request):
        serializer = GenerarPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        estudiante = get_object_or_404(
            academic_selectors.estudiantes_visibles(request.user),
            pk=serializer.validated_data["estudiante"],
        )
        plan = services.generar_plan(
            request.user,
            estudiante,
            serializer.validated_data["asignatura"],
            serializer.validated_data.get("temas_manuales"),
        )
        return self._responder(request, plan.id, status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        plan = services.aprobar_plan(self.get_object(), request.user)
        return self._responder(request, plan.id)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        plan = services.cancelar_plan(self.get_object(), request.user)
        return self._responder(request, plan.id)

    @action(detail=True, methods=["post"])
    def revisar(self, request, pk=None):
        plan = services.marcar_revisado(self.get_object(), request.user)
        return self._responder(request, plan.id)


class TemaPlanViewSet(viewsets.GenericViewSet):
    """
    Edición de un tema del plan (solo docente, solo mientras el plan es una propuesta).
      PATCH /{id}/               {"objetivo": "..."}
      POST  /{id}/actividades/   {"recurso": id}  o  {"titulo": "...", "instrucciones": "..."}
    """

    permission_classes = [IsDocente]
    serializer_class = TemaPlanSerializer

    def get_queryset(self):
        return selectors.temas_plan_visibles(self.request.user)

    def partial_update(self, request, pk=None):
        tema_plan = self.get_object()
        services.verificar_editable(tema_plan.plan)
        serializer = TemaPlanEditarSerializer(tema_plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(TemaPlanSerializer(self.get_queryset().get(pk=tema_plan.pk)).data)

    @action(detail=True, methods=["post"], url_path="actividades")
    def agregar_actividad(self, request, pk=None):
        tema_plan = self.get_object()
        serializer = AgregarActividadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actividad = services.agregar_actividad(tema_plan, **serializer.validated_data)
        return Response(
            ActividadRefuerzoSerializer(actividad).data, status=status.HTTP_201_CREATED
        )


class ActividadRefuerzoViewSet(viewsets.GenericViewSet):
    """
    Actividades de un plan.
      PATCH  /{id}/          (docente, solo en propuesta) edita título, instrucciones o duración
      DELETE /{id}/          (docente, solo en propuesta) quita la actividad
      POST   /{id}/cumplir/  (docente o representante, plan aprobado) marca como cumplida
      POST   /{id}/reabrir/  (solo docente) corrige un cumplimiento marcado por error
      GET    /{id}/evidencias/  (docente o representante) fotos de la actividad
      POST   /{id}/evidencias/  (representante, multipart «archivo» + «comentario») sube una foto
    """

    serializer_class = ActividadRefuerzoSerializer
    parser_classes = [JSONParser, MultiPartParser]

    def get_permissions(self):
        if self.action in ("cumplir", "evidencias"):
            return [IsDocenteOrRepresentante()]
        return [IsDocente()]

    def get_queryset(self):
        return selectors.actividades_refuerzo_visibles(self.request.user)

    def partial_update(self, request, pk=None):
        actividad = self.get_object()
        services.verificar_editable(actividad.tema_plan.plan)
        serializer = ActividadRefuerzoEditarSerializer(actividad, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ActividadRefuerzoSerializer(actividad).data)

    def destroy(self, request, pk=None):
        actividad = self.get_object()
        services.verificar_editable(actividad.tema_plan.plan)
        actividad.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _respuesta_seguimiento(self, actividad, plan):
        datos = dict(ActividadRefuerzoSerializer(actividad).data)
        datos["plan_estado"] = plan.estado
        return Response(datos)

    @action(detail=True, methods=["post"])
    def cumplir(self, request, pk=None):
        actividad, plan = services.cumplir_actividad(self.get_object(), request.user)
        return self._respuesta_seguimiento(actividad, plan)

    @action(detail=True, methods=["get", "post"])
    def evidencias(self, request, pk=None):
        actividad = self.get_object()
        if request.method == "POST":
            evidencias.subir(
                actividad, request.user, request.FILES.get("archivo"), request.data.get("comentario", "")
            )
            actividad = self.get_queryset().get(pk=actividad.pk)
            return Response(
                EvidenciaSerializer(actividad.evidencias.all(), many=True).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(EvidenciaSerializer(actividad.evidencias.all(), many=True).data)

    @action(detail=True, methods=["post"])
    def reabrir(self, request, pk=None):
        actividad, plan = services.reabrir_actividad(self.get_object(), request.user)
        return self._respuesta_seguimiento(actividad, plan)


class AlertaTempranaView(APIView):
    """GET: tablero de alerta temprana institucional (solo administrador)."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        return Response(alerta.alerta_temprana())


class EvidenciaViewSet(viewsets.GenericViewSet):
    """
    Evidencias fotográficas (mejora 14).
      GET    /{id}/archivo/  (docente o representante del plan) entrega la foto
      DELETE /{id}/          (quien la subió, plan en curso) la elimina
    Las fotos nunca tienen URL pública: se entregan solo por aquí, con autenticación.
    """

    serializer_class = EvidenciaSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [IsRepresentante()]
        return [IsDocenteOrRepresentante()]

    def get_queryset(self):
        return selectors.evidencias_visibles(self.request.user)

    def destroy(self, request, pk=None):
        evidencias.eliminar(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        evidencia = self.get_object()
        respuesta = FileResponse(evidencia.archivo.open("rb"), content_type="image/jpeg")
        respuesta["Cache-Control"] = "private, max-age=300"
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta
