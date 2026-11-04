"""
Reportes descargables (PDF / Excel).

GET /api/reports/
    Catálogo de reportes que puede descargar el usuario según su rol, con los filtros que
    acepta cada uno y las opciones (paralelos, asignaturas, estudiantes) que puede ver.

GET /api/reports/<clave>/?formato=pdf|xlsx&paralelo=&asignatura=&estudiante=
                         &estado_dificultad=&estado_plan=&desde=AAAA-MM-DD&hasta=AAAA-MM-DD
    Descarga el reporte. Los filtros se validan contra lo que el usuario puede ver.
"""

from datetime import date

from django.http import Http404, HttpResponse
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academic import selectors as academic
from apps.academic.models import Asignatura
from apps.grades.models import Dificultad
from apps.reinforcement.models import PlanRefuerzo
from apps.security.permissions import IsPasswordUpToDate

from . import datos, exportar


def _opciones(user):
    paralelos = academic.paralelos_visibles(user).filter(is_active=True).order_by("grado__orden", "nombre")
    asignaturas = Asignatura.objects.filter(
        is_active=True, id__in=academic.asignaciones_visibles(user).filter(is_active=True).values("asignatura_id")
    ).order_by("nombre")
    estudiantes = (
        academic.estudiantes_visibles(user).filter(is_active=True)
        .order_by("paralelo__grado__orden", "paralelo__nombre", "last_name", "first_name")
    )
    return {
        "paralelo": [{"id": p.id, "nombre": p.nombre_completo} for p in paralelos],
        "asignatura": [{"id": a.id, "nombre": a.nombre} for a in asignaturas],
        "estudiante": [
            {"id": e.id, "nombre": f"{e.last_name} {e.first_name}", "paralelo": e.paralelo.nombre_completo}
            for e in estudiantes
        ],
        "estado_dificultad": [{"id": v, "nombre": n} for v, n in Dificultad.Estado.choices],
        "estado_plan": [{"id": v, "nombre": n} for v, n in PlanRefuerzo.Estado.choices],
    }


class CatalogoReportesView(APIView):
    permission_classes = [IsPasswordUpToDate]

    def get(self, request):
        user = request.user
        reportes = [
            {
                "clave": d.clave,
                "titulo": d.titulo,
                "descripcion": d.descripcion,
                "filtros": list(d.filtros),
                "requeridos": list(d.requeridos),
                "formatos": datos.formatos_para(user, d),
            }
            for d in datos.definiciones_para(user)
        ]
        usados = {f for r in reportes for f in r["filtros"]}
        opciones = {k: v for k, v in _opciones(user).items() if k in usados}
        return Response({"reportes": reportes, "opciones": opciones})


class DescargarReporteView(APIView):
    permission_classes = [IsPasswordUpToDate]

    def get(self, request, clave):
        user = request.user
        definicion = datos.CATALOGO.get(clave)
        if definicion is None:
            raise Http404
        if user.role not in definicion.roles:
            raise PermissionDenied("Tu rol no puede descargar este reporte.")

        formato = request.query_params.get("formato", "pdf").lower()
        if formato not in datos.formatos_para(user, definicion):
            raise ValidationError({"formato": "Formato no disponible para este reporte."})

        filtros, etiquetas = self._filtros(user, definicion, request.query_params)
        reporte = datos.construir(user, definicion, filtros, etiquetas)
        contenido = exportar.EXPORTADORES[formato](reporte)

        respuesta = HttpResponse(contenido, content_type=exportar.CONTENT_TYPES[formato])
        respuesta["Content-Disposition"] = f'attachment; filename="{exportar.nombre_archivo(reporte, formato)}"'
        respuesta["Cache-Control"] = "no-store"
        return respuesta

    # --- Validación de filtros ------------------------------------------------
    @staticmethod
    def _id(params, nombre):
        valor = params.get(nombre)
        if not valor:
            return None
        if not str(valor).isdigit():
            raise ValidationError({nombre: "Debe ser un número."})
        return int(valor)

    @staticmethod
    def _fecha(params, nombre):
        valor = params.get(nombre)
        if not valor:
            return None
        try:
            return date.fromisoformat(valor)
        except ValueError:
            raise ValidationError({nombre: "Usa el formato AAAA-MM-DD."}) from None

    def _filtros(self, user, definicion, params):
        filtros, etiquetas = {}, []
        permitidos = set(definicion.filtros)

        for nombre in definicion.requeridos:
            if not params.get(nombre):
                raise ValidationError({nombre: "Este filtro es obligatorio."})

        if "paralelo" in permitidos and (pid := self._id(params, "paralelo")):
            paralelo = academic.paralelos_visibles(user).filter(pk=pid).first()
            if paralelo is None:
                raise ValidationError({"paralelo": "Paralelo no encontrado."})
            filtros["paralelo"] = paralelo
            etiquetas.append(("Paralelo", paralelo.nombre_completo))

        if "asignatura" in permitidos and (aid := self._id(params, "asignatura")):
            asignatura = Asignatura.objects.filter(pk=aid).first()
            if asignatura is None:
                raise ValidationError({"asignatura": "Asignatura no encontrada."})
            filtros["asignatura"] = asignatura
            etiquetas.append(("Asignatura", asignatura.nombre))

        if "estudiante" in permitidos and (eid := self._id(params, "estudiante")):
            estudiante = academic.estudiantes_visibles(user).filter(pk=eid, is_active=True).first()
            if estudiante is None:
                raise Http404  # no se revela si existe
            filtros["estudiante"] = estudiante
            etiquetas += [
                ("Estudiante", estudiante.full_name),
                ("Paralelo", estudiante.paralelo.nombre_completo),
                ("Representante", estudiante.representante.full_name),
            ]

        for nombre, opciones, etiqueta in (
            ("estado_dificultad", Dificultad.Estado, "Estado"),
            ("estado_plan", PlanRefuerzo.Estado, "Estado"),
        ):
            valor = params.get(nombre)
            if nombre in permitidos and valor:
                if valor not in opciones.values:
                    raise ValidationError({nombre: "Estado no válido."})
                filtros[nombre] = valor
                etiquetas.append((etiqueta, opciones(valor).label))

        if "desde" in permitidos:
            desde, hasta = self._fecha(params, "desde"), self._fecha(params, "hasta")
            if desde and hasta and desde > hasta:
                raise ValidationError({"hasta": "Debe ser posterior a «desde»."})
            if desde:
                filtros["desde"] = desde
                etiquetas.append(("Desde", desde))
            if hasta:
                filtros["hasta"] = hasta
                etiquetas.append(("Hasta", hasta))
        return filtros, etiquetas
