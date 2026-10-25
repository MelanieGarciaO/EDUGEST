"""
Tablero de alerta temprana institucional (mejora 10, rol administrador).

Indicadores agregados (sin datos personales de estudiantes):
1. Asignaturas con más estudiantes en refuerzo (dificultad vigente o plan activo).
2. Paralelos con menor rendimiento (promedio de todas sus notas).
3. Temas con mayor índice de dificultad (% de estudiantes calificados con dificultad).
Además, un resumen general: estudiantes con dificultad, reincidentes, planes activos y
porcentaje de planes revisados por la familia.

Solo cuenta estudiantes activos y temas de los grados habilitados.
"""

from django.db.models import Avg, Count, Q

from apps.academic.grados import grado_maximo, grado_minimo
from apps.academic.models import Estudiante
from apps.grades import scale
from apps.grades.models import Calificacion, Dificultad

from .models import PlanRefuerzo

LIMITE = 5


def _pct(parte, total):
    return round(parte * 100 / total, 1) if total else 0.0


def alerta_temprana(limite=LIMITE):
    rango = {"tema__grado__orden__gte": grado_minimo(), "tema__grado__orden__lte": grado_maximo()}
    activos = {"estudiante__is_active": True}

    dificultades = Dificultad.objects.filter(estado=Dificultad.Estado.DETECTADA, **rango, **activos)
    califs = Calificacion.objects.filter(**rango, **activos)
    planes_activos = PlanRefuerzo.objects.filter(
        estado__in=[PlanRefuerzo.Estado.APROBADA, PlanRefuerzo.Estado.COMPLETADA],
        estudiante__is_active=True,
    )
    publicados = PlanRefuerzo.objects.exclude(
        estado__in=[PlanRefuerzo.Estado.PROPUESTA, PlanRefuerzo.Estado.CANCELADA]
    ).filter(estudiante__is_active=True)

    total_estudiantes = Estudiante.objects.filter(
        is_active=True,
        paralelo__grado__orden__gte=grado_minimo(),
        paralelo__grado__orden__lte=grado_maximo(),
    ).count()
    con_dificultad = dificultades.values("estudiante").distinct().count()

    # 1) Asignaturas con más estudiantes en refuerzo.
    en_refuerzo = {}
    for fila in dificultades.values("tema__asignatura_id", "tema__asignatura__nombre", "estudiante_id"):
        clave = (fila["tema__asignatura_id"], fila["tema__asignatura__nombre"])
        en_refuerzo.setdefault(clave, set()).add(fila["estudiante_id"])
    for fila in planes_activos.filter(estado=PlanRefuerzo.Estado.APROBADA).values(
        "asignatura_id", "asignatura__nombre", "estudiante_id"
    ):
        clave = (fila["asignatura_id"], fila["asignatura__nombre"])
        en_refuerzo.setdefault(clave, set()).add(fila["estudiante_id"])
    asignaturas = sorted(
        (
            {"asignatura": a_id, "nombre": nombre, "estudiantes": len(ests)}
            for (a_id, nombre), ests in en_refuerzo.items()
        ),
        key=lambda x: (-x["estudiantes"], x["nombre"]),
    )[:limite]

    # 2) Paralelos con menor rendimiento.
    paralelos = []
    for fila in (
        califs.values(
            "estudiante__paralelo_id",
            "estudiante__paralelo__nombre",
            "estudiante__paralelo__grado__nombre",
            "estudiante__paralelo__grado__orden",
        )
        .annotate(promedio=Avg("valor"), notas=Count("id"))
        .order_by("promedio", "estudiante__paralelo__grado__orden", "estudiante__paralelo__nombre")[:limite]
    ):
        prom = scale.promedio([fila["promedio"]])
        paralelos.append(
            {
                "paralelo": fila["estudiante__paralelo_id"],
                "nombre": f"{fila['estudiante__paralelo__grado__nombre']} {fila['estudiante__paralelo__nombre']}",
                "promedio": str(prom),
                "nivel": scale.nivel_cualitativo(prom),
                "notas": fila["notas"],
            }
        )

    # 3) Temas con mayor índice de dificultad.
    calificados = {
        f["tema_id"]: f["n"]
        for f in califs.values("tema_id").annotate(n=Count("estudiante", distinct=True))
    }
    temas = []
    for fila in dificultades.values(
        "tema_id", "tema__nombre", "tema__asignatura__nombre", "tema__grado__nombre"
    ).annotate(
        con_dificultad=Count("estudiante", distinct=True),
        reincidentes=Count("estudiante", filter=Q(veces_detectada__gt=1), distinct=True),
    ):
        total = calificados.get(fila["tema_id"], 0)
        temas.append(
            {
                "tema": fila["tema_id"],
                "nombre": fila["tema__nombre"],
                "asignatura": fila["tema__asignatura__nombre"],
                "grado": fila["tema__grado__nombre"],
                "con_dificultad": fila["con_dificultad"],
                "calificados": total,
                "indice": _pct(fila["con_dificultad"], total),
                "reincidentes": fila["reincidentes"],
            }
        )
    temas.sort(key=lambda t: (-t["indice"], -t["con_dificultad"], t["nombre"]))

    total_publicados = publicados.count()
    return {
        "resumen": {
            "estudiantes": total_estudiantes,
            "con_dificultad": con_dificultad,
            "porcentaje_con_dificultad": _pct(con_dificultad, total_estudiantes),
            "reincidentes": dificultades.filter(veces_detectada__gt=1)
            .values("estudiante")
            .distinct()
            .count(),
            "planes_en_curso": planes_activos.filter(estado=PlanRefuerzo.Estado.APROBADA).count(),
            "planes_revisados_por_familia": _pct(
                publicados.filter(revisado_en__isnull=False).count(), total_publicados
            ),
        },
        "asignaturas_en_refuerzo": asignaturas,
        "paralelos_menor_rendimiento": paralelos,
        "temas_mayor_dificultad": temas[:limite],
    }
