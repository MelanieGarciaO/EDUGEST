from django.apps import apps
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academic import selectors as academic_selectors
from apps.academic.models import Estudiante
from apps.academic.views import filter_by_id
from apps.activities import selectors as activities_selectors
from apps.security.permissions import IsDocente, IsDocenteOrAdministrador, IsPasswordUpToDate

from . import excel, scale, services
from .models import Calificacion, Dificultad
from .selectors import calificaciones_visibles, dificultades_visibles
from .serializers import (
    CalificacionSerializer,
    DificultadSerializer,
    GuardarCalificacionesSerializer,
    HistorialSerializer,
)


class ActividadCalificacionesView(APIView):
    """
    Notas de una actividad.

    GET  (docente dueño o administrador): lista de estudiantes del paralelo con su nota
         (o "sin calificar").
    POST (solo el docente dueño): guarda en una sola operación las notas de varios
         estudiantes y las asocia a un tema. Si el estudiante ya tenía nota, la corrige y
         deja historial.
         Cuerpo: {"tema": 3, "calificaciones": [{"estudiante": 10, "valor": "8.50"}, ...]}
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsDocente()]
        return [IsDocenteOrAdministrador()]

    def _actividad(self, request, actividad_id):
        # Para el docente son solo las suyas; para el administrador, todas.
        qs = activities_selectors.actividades_visibles(request.user)
        return get_object_or_404(qs, pk=actividad_id)

    def get(self, request, actividad_id):
        actividad = self._actividad(request, actividad_id)
        paralelo = actividad.asignacion.paralelo
        estudiantes = Estudiante.objects.filter(paralelo=paralelo, is_active=True).order_by(
            "last_name", "first_name"
        )
        notas = {
            c.estudiante_id: c
            for c in Calificacion.objects.filter(actividad=actividad).select_related("tema")
        }

        filas = []
        for estudiante in estudiantes:
            c = notas.get(estudiante.id)
            nivel = scale.nivel_cualitativo(c.valor) if c else None
            filas.append(
                {
                    "estudiante": estudiante.id,
                    "estudiante_nombre": estudiante.full_name,
                    "calificacion": c.id if c else None,
                    "valor": str(c.valor) if c else None,
                    "tema": c.tema_id if c else None,
                    "tema_nombre": c.tema.nombre if c else None,
                    "nivel": nivel,
                    "nivel_nombre": scale.nombre_nivel(nivel),
                }
            )

        calificados = [c for c in notas.values() if c.estudiante_id in {e.id for e in estudiantes}]
        prom = scale.promedio(c.valor for c in calificados)
        return Response(
            {
                "actividad": {
                    "id": actividad.id,
                    "descripcion": actividad.descripcion,
                    "fecha_entrega": actividad.fecha_entrega,
                    "asignatura_nombre": actividad.asignacion.asignatura.nombre,
                    "paralelo_nombre": paralelo.nombre_completo,
                    "vigencia": actividad.vigencia(timezone.localdate()),
                },
                "resumen": {
                    "estudiantes": len(filas),
                    "calificados": len(calificados),
                    "sin_calificar": len(filas) - len(calificados),
                    "promedio": str(prom) if prom is not None else None,
                },
                "calificaciones": filas,
            }
        )

    def post(self, request, actividad_id):
        actividad = self._actividad(request, actividad_id)
        services.verificar_calificable(actividad)

        serializer = GuardarCalificacionesSerializer(
            data=request.data, context={"request": request, "actividad": actividad}
        )
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data

        resultado = services.guardar_calificaciones(
            actividad,
            datos["tema"],
            [(i["estudiante"], i["valor"]) for i in datos["calificaciones"]],
            request.user,
        )
        guardadas = calificaciones_visibles(request.user).filter(
            pk__in=resultado["calificaciones_ids"]
        )
        return Response(
            {
                "creadas": resultado["creadas"],
                "actualizadas": resultado["actualizadas"],
                "sin_cambios": resultado["sin_cambios"],
                "calificaciones": CalificacionSerializer(
                    guardadas.order_by("estudiante__last_name", "estudiante__first_name"),
                    many=True,
                    context={"request": request},
                ).data,
                "dificultades": DificultadSerializer(
                    resultado["dificultades"], many=True, context={"request": request}
                ).data,
            }
        )


class _ActividadDocenteMixin:
    """Actividad del docente autenticado y estudiantes activos de su paralelo."""

    permission_classes = [IsDocente]

    def _actividad_y_estudiantes(self, request, actividad_id):
        actividad = get_object_or_404(
            activities_selectors.actividades_visibles(request.user).select_related(
                "asignacion__asignatura", "asignacion__paralelo__grado"
            ),
            pk=actividad_id,
        )
        estudiantes = Estudiante.objects.filter(
            paralelo=actividad.asignacion.paralelo, is_active=True
        ).order_by("last_name", "first_name")
        return actividad, estudiantes


class PlantillaCalificacionesView(_ActividadDocenteMixin, APIView):
    """GET: descarga la plantilla Excel de la actividad (nómina + notas actuales)."""

    def get(self, request, actividad_id):
        actividad, estudiantes = self._actividad_y_estudiantes(request, actividad_id)
        notas = dict(
            Calificacion.objects.filter(actividad=actividad).values_list("estudiante_id", "valor")
        )
        contenido = excel.generar_plantilla(actividad, estudiantes, notas)
        respuesta = HttpResponse(contenido, content_type=excel.CONTENT_TYPE)
        respuesta["Content-Disposition"] = f'attachment; filename="{excel.nombre_archivo(actividad)}"'
        return respuesta


class ImportarCalificacionesView(_ActividadDocenteMixin, APIView):
    """
    POST (multipart, campo «archivo»): valida la plantilla llena y devuelve una vista
    previa de las notas. NO guarda: el docente revisa y guarda con el flujo normal.
    """

    parser_classes = [MultiPartParser]

    def post(self, request, actividad_id):
        actividad, estudiantes = self._actividad_y_estudiantes(request, actividad_id)
        services.verificar_calificable(actividad)
        return Response(excel.leer_plantilla(request.FILES.get("archivo"), actividad, estudiantes))


class CalificacionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de notas según el rol.
    Filtros: ?estudiante= ?actividad= ?asignatura= ?tema= ?paralelo=
    Acción: GET /{id}/historial/ (docente dueño y administrador).
    """

    serializer_class = CalificacionSerializer

    def get_permissions(self):
        if self.action == "historial":
            return [IsDocenteOrAdministrador()]
        return [IsPasswordUpToDate()]

    def get_queryset(self):
        params = self.request.query_params
        qs = calificaciones_visibles(self.request.user)
        qs = filter_by_id(qs, params, "estudiante", "estudiante_id")
        qs = filter_by_id(qs, params, "actividad", "actividad_id")
        qs = filter_by_id(qs, params, "asignatura", "actividad__asignacion__asignatura_id")
        qs = filter_by_id(qs, params, "tema", "tema_id")
        qs = filter_by_id(qs, params, "paralelo", "estudiante__paralelo_id")
        return qs.order_by("-actividad__fecha_entrega", "estudiante__last_name", "id")

    @action(detail=True, methods=["get"])
    def historial(self, request, pk=None):
        calificacion = self.get_object()
        registros = calificacion.historial.select_related(
            "tema_anterior", "tema_nuevo", "modificado_por"
        )
        return Response(HistorialSerializer(registros, many=True).data)


class DesempenoEstudianteView(APIView):
    """
    Desempeño de un estudiante por asignatura y tema (con subtemas), con promedio y nivel
    cualitativo. El docente solo ve sus asignaturas; el representante, todas las de su
    estudiante.
    """

    permission_classes = [IsPasswordUpToDate]

    def get(self, request, estudiante_id):
        estudiante = get_object_or_404(
            academic_selectors.estudiantes_visibles(request.user), pk=estudiante_id
        )
        return Response(services.desempeno_estudiante(estudiante, request.user))


class DificultadViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Dificultades detectadas según el rol.
    Filtros: ?estado=DETECTADA|SUPERADA ?nivel=MODERADA|ALTA ?reincidente=true|false ?estudiante= ?paralelo=
             ?asignatura= ?tema=
    """

    serializer_class = DificultadSerializer
    permission_classes = [IsPasswordUpToDate]

    def get_queryset(self):
        params = self.request.query_params
        qs = dificultades_visibles(self.request.user)

        estado = params.get("estado")
        if estado:
            estado = estado.upper()
            if estado not in Dificultad.Estado.values:
                raise ValidationError({"estado": "Valores válidos: DETECTADA, SUPERADA."})
            qs = qs.filter(estado=estado)

        nivel = params.get("nivel")
        if nivel:
            nivel = nivel.upper()
            if nivel not in Dificultad.Nivel.values:
                raise ValidationError({"nivel": "Valores válidos: MODERADA, ALTA."})
            qs = qs.filter(nivel=nivel)

        reincidente = params.get("reincidente")
        if reincidente:
            reincidente = reincidente.lower()
            if reincidente not in ("true", "false"):
                raise ValidationError({"reincidente": "Valores válidos: true, false."})
            qs = qs.filter(veces_detectada__gt=1) if reincidente == "true" else qs.filter(veces_detectada=1)

        qs = filter_by_id(qs, params, "estudiante", "estudiante_id")
        qs = filter_by_id(qs, params, "paralelo", "estudiante__paralelo_id")
        qs = filter_by_id(qs, params, "asignatura", "tema__asignatura_id")
        qs = filter_by_id(qs, params, "tema", "tema_id")
        return self._con_refuerzo(qs).order_by("-updated_at", "-id")

    @staticmethod
    def _con_refuerzo(qs):
        """
        Marca las dificultades cuyo tema está en un plan de refuerzo completado y aún sin
        evaluar. Se usa get_model para que `grades` no importe el módulo de refuerzo.
        """
        TemaPlan = apps.get_model("reinforcement", "TemaPlan")
        pendientes = TemaPlan.objects.filter(
            plan__estudiante_id=OuterRef("estudiante_id"),
            tema_id=OuterRef("tema_id"),
            plan__estado="COMPLETADA",
            superado__isnull=True,
        )
        en_curso = TemaPlan.objects.filter(
            plan__estudiante_id=OuterRef("estudiante_id"),
            tema_id=OuterRef("tema_id"),
            plan__estado__in=["PROPUESTA", "APROBADA"],
        )
        return qs.annotate(
            refuerzo_pendiente_evaluacion=Exists(pendientes),
            refuerzo_en_curso=Exists(en_curso),
        )
