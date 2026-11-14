"""
Datos de los reportes descargables.

Cada reporte se arma como una estructura neutra (Reporte -> Secciones -> filas) que luego
se exporta a PDF o Excel (ver exportar.py). La visibilidad por rol NO se repite aquí: se
usan los selectores de cada módulo, así un usuario descarga exactamente lo que ve en pantalla.

Reportes por rol:
    Docente        calificaciones, dificultades, planes, avance
    Administrador  resumen, calificaciones, dificultades, planes, avance
    Representante  avance (de sus representados)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from django.db.models import Count
from django.utils import timezone

from apps.academic import selectors as academic
from apps.academic.models import Tema
from apps.activities.models import Actividad
from apps.grades import scale
from apps.grades import selectors as grades
from apps.grades.models import Dificultad
from apps.reinforcement import selectors as refuerzo
from apps.reinforcement.models import ActividadRefuerzo, PlanRefuerzo
from apps.security.models import Role

DOCENTE, ADMIN, REPRESENTANTE = Role.DOCENTE, Role.ADMINISTRADOR, Role.REPRESENTANTE
MAX_FILAS = 5000  # protege al servidor y mantiene el PDF manejable


# ---------------------------------------------------------------------------
# Estructura neutra
# ---------------------------------------------------------------------------
@dataclass
class Seccion:
    titulo: str
    columnas: list  # [(encabezado, peso_de_ancho)]
    filas: list = field(default_factory=list)
    vacio: str = "Sin datos para los filtros seleccionados."
    nota: str = ""


@dataclass
class Reporte:
    clave: str
    titulo: str
    descripcion: str
    filtros: list  # [(etiqueta, valor)] mostrados en el encabezado
    secciones: list
    generado_por: str = ""
    generado_en: datetime = field(default_factory=timezone.localtime)


@dataclass(frozen=True)
class Definicion:
    clave: str
    titulo: str
    descripcion: str
    roles: tuple
    filtros: tuple  # paralelo, asignatura, estudiante, estado_dificultad, estado_plan, desde, hasta
    requeridos: tuple = ()
    formatos_representante: tuple = ("pdf",)


CATALOGO = {
    d.clave: d
    for d in (
        Definicion(
            "resumen", "Resumen institucional",
            "Rendimiento, dificultades y planes por paralelo y asignatura, y los temas con más dificultades.",
            (ADMIN,), (),
        ),
        Definicion(
            "calificaciones", "Calificaciones",
            "Promedio y nivel de logro por estudiante y asignatura, con el detalle de cada nota.",
            (DOCENTE, ADMIN), ("paralelo", "asignatura", "desde", "hasta"),
        ),
        Definicion(
            "dificultades", "Estudiantes con dificultades",
            "Estudiantes con promedio menor a 7,00 en un tema, su nivel y si son reincidentes.",
            (DOCENTE, ADMIN), ("paralelo", "asignatura", "estado_dificultad"),
        ),
        Definicion(
            "planes", "Planes de refuerzo",
            "Estado y avance de los planes de refuerzo, y el resultado de cada tema.",
            (DOCENTE, ADMIN), ("paralelo", "asignatura", "estado_plan"),
        ),
        Definicion(
            "avance", "Avance del estudiante",
            "Promedios por asignatura y tema, dificultades y planes de refuerzo de un estudiante.",
            (DOCENTE, ADMIN, REPRESENTANTE), ("estudiante",), requeridos=("estudiante",),
        ),
    )
}


def definiciones_para(user):
    return [d for d in CATALOGO.values() if user.role in d.roles]


def formatos_para(user, definicion):
    if user.role == REPRESENTANTE:
        return list(definicion.formatos_representante)
    return ["pdf", "xlsx"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _nivel(promedio):
    return scale.nombre_nivel(scale.nivel_cualitativo(promedio)) or ""


def _fecha(valor):
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date()
    return valor


def _si_no(valor):
    return "Sí" if valor else "No"


def _limitar(seccion):
    if len(seccion.filas) > MAX_FILAS:
        seccion.filas = seccion.filas[:MAX_FILAS]
        seccion.nota = f"Se muestran solo las primeras {MAX_FILAS} filas. Usa filtros para acotar."
    return seccion


def _orden_estudiante(e):
    return (e.last_name.lower(), e.first_name.lower())


# ---------------------------------------------------------------------------
# Reportes
# ---------------------------------------------------------------------------
def calificaciones(user, f):
    qs = grades.calificaciones_visibles(user).select_related(
        "estudiante__paralelo__grado", "actividad", "tema__padre"
    ).filter(estudiante__is_active=True)
    if f.get("paralelo"):
        qs = qs.filter(estudiante__paralelo=f["paralelo"])
    if f.get("asignatura"):
        qs = qs.filter(actividad__asignacion__asignatura=f["asignatura"])
    if f.get("desde"):
        qs = qs.filter(actividad__fecha_entrega__gte=f["desde"])
    if f.get("hasta"):
        qs = qs.filter(actividad__fecha_entrega__lte=f["hasta"])
    notas = list(qs)

    grupos = defaultdict(list)
    for c in notas:
        grupos[(c.estudiante, c.actividad.asignacion.asignatura.nombre)].append(c.valor)
    resumen = Seccion(
        "Promedio por estudiante",
        [("Estudiante", 3), ("Paralelo", 2), ("Asignatura", 2.5), ("N.º notas", 1), ("Promedio", 1.2), ("Nivel de logro", 3)],
    )
    for (est, asig), valores in sorted(grupos.items(), key=lambda x: (x[0][1], _orden_estudiante(x[0][0]))):
        prom = scale.promedio(valores)
        resumen.filas.append([est.full_name, est.paralelo.nombre_completo, asig, len(valores), prom, _nivel(prom)])

    detalle = Seccion(
        "Detalle de notas",
        [("Entrega", 1.2), ("Estudiante", 2.3), ("Asignatura", 1.8), ("Tema", 2.2), ("Actividad", 3.2),
         ("Nota", 0.9), ("Observación", 3.2)],
    )
    notas.sort(key=lambda c: (c.actividad.fecha_entrega, _orden_estudiante(c.estudiante)))
    for c in notas:
        detalle.filas.append([
            c.actividad.fecha_entrega, c.estudiante.full_name, c.actividad.asignacion.asignatura.nombre,
            str(c.tema), c.actividad.descripcion[:120], c.valor, c.observacion,
        ])
    return [_limitar(resumen), _limitar(detalle)]


def dificultades(user, f):
    qs = grades.dificultades_visibles(user).filter(estudiante__is_active=True)
    if f.get("paralelo"):
        qs = qs.filter(estudiante__paralelo=f["paralelo"])
    if f.get("asignatura"):
        qs = qs.filter(tema__asignatura=f["asignatura"])
    if f.get("estado_dificultad"):
        qs = qs.filter(estado=f["estado_dificultad"])
    seccion = Seccion(
        "Dificultades por tema",
        [("Estudiante", 2.6), ("Paralelo", 1.8), ("Asignatura", 2), ("Tema", 2.8), ("Promedio", 1),
         ("N.º notas", 0.9), ("Nivel", 1.1), ("Estado", 1.1), ("Reincidente", 1), ("Detectada", 1.2)],
    )
    for d in sorted(qs, key=lambda d: (d.tema.asignatura.nombre, d.promedio, _orden_estudiante(d.estudiante))):
        seccion.filas.append([
            d.estudiante.full_name, d.estudiante.paralelo.nombre_completo, d.tema.asignatura.nombre, str(d.tema),
            d.promedio, d.num_calificaciones, d.get_nivel_display(), d.get_estado_display(),
            _si_no(d.reincidente), _fecha(d.detectada_en),
        ])
    return [_limitar(seccion)]


def _avance_plan(plan):
    acts = [a for t in plan.temas.all() for a in t.actividades.all()]
    cumplidas = sum(a.estado == ActividadRefuerzo.Estado.CUMPLIDA for a in acts)
    temas = list(plan.temas.all())
    superados = sum(bool(t.superado) for t in temas)
    pct = round(cumplidas * 100 / len(acts)) if acts else 0
    return cumplidas, len(acts), pct, superados, len(temas)


def planes(user, f):
    qs = refuerzo.planes_visibles(user).filter(estudiante__is_active=True)
    if f.get("paralelo"):
        qs = qs.filter(estudiante__paralelo=f["paralelo"])
    if f.get("asignatura"):
        qs = qs.filter(asignatura=f["asignatura"])
    if f.get("estado_plan"):
        qs = qs.filter(estado=f["estado_plan"])
    planes_ = sorted(qs, key=lambda p: (p.asignatura.nombre, _orden_estudiante(p.estudiante)))

    general = Seccion(
        "Planes",
        [("Estudiante", 2.6), ("Paralelo", 1.8), ("Asignatura", 2), ("Docente", 2.2), ("Nivel", 1),
         ("Estado", 1.2), ("Actividades", 1.2), ("Avance %", 1), ("Temas superados", 1.3),
         ("Revisado por familia", 1.4), ("Creado", 1.2)],
    )
    apoyos = Seccion(
        "Apoyos DUA por tema",
        [("Estudiante", 2.2), ("Asignatura", 1.6), ("Tema", 2), ("Implicación", 3.2),
         ("Representación", 3.2), ("Acción y expresión", 3.2), ("Origen", 1.3)],
    )
    temas = Seccion(
        "Resultado por tema",
        [("Estudiante", 2.6), ("Asignatura", 2), ("Tema", 3), ("Dificultad", 1.2),
         ("Promedio inicial", 1.3), ("Promedio final", 1.3), ("Superado", 1)],
    )
    for p in planes_:
        cumplidas, total, pct, superados, n_temas = _avance_plan(p)
        general.filas.append([
            p.estudiante.full_name, p.estudiante.paralelo.nombre_completo, p.asignatura.nombre,
            p.docente.full_name, p.get_nivel_display(), p.get_estado_display(), f"{cumplidas}/{total}", pct,
            f"{superados}/{n_temas}", _fecha(p.revisado_en) or "No", _fecha(p.created_at),
        ])
        for t in p.temas.all():
            superado = "Pendiente" if t.superado is None else _si_no(t.superado)
            temas.filas.append([
                p.estudiante.full_name, p.asignatura.nombre, str(t.tema), t.nivel_dificultad.capitalize(),
                t.promedio_inicial if t.promedio_inicial is not None else "",
                t.promedio_final if t.promedio_final is not None else "", superado,
            ])
            apoyos.filas.append([
                p.estudiante.full_name, p.asignatura.nombre, str(t.tema), t.dua_implicacion,
                t.dua_representacion, t.dua_accion_expresion, t.get_dua_origen_display(),
            ])
    return [_limitar(general), _limitar(temas), _limitar(apoyos)]


def avance(user, f):
    est = f["estudiante"]
    notas = list(grades.calificaciones_visibles(user).filter(estudiante=est).select_related("tema__padre"))

    por_asig, por_tema = defaultdict(list), defaultdict(list)
    for c in notas:
        asig = c.actividad.asignacion.asignatura.nombre
        por_asig[asig].append(c.valor)
        por_tema[(asig, str(c.tema))].append(c.valor)

    s_asig = Seccion(
        "Promedio por asignatura",
        [("Asignatura", 3), ("N.º notas", 1), ("Promedio", 1), ("Nivel de logro", 3.5)],
        vacio="Todavía no hay notas registradas.",
    )
    for asig in sorted(por_asig):
        prom = scale.promedio(por_asig[asig])
        s_asig.filas.append([asig, len(por_asig[asig]), prom, _nivel(prom)])

    s_tema = Seccion(
        "Promedio por tema",
        [("Asignatura", 2.5), ("Tema", 3.5), ("N.º notas", 1), ("Promedio", 1), ("Nivel de logro", 3)],
        vacio="Todavía no hay notas registradas.",
    )
    for (asig, tema) in sorted(por_tema):
        prom = scale.promedio(por_tema[(asig, tema)])
        s_tema.filas.append([asig, tema, len(por_tema[(asig, tema)]), prom, _nivel(prom)])

    s_dif = Seccion(
        "Dificultades vigentes",
        [("Asignatura", 2.5), ("Tema", 3.5), ("Promedio", 1), ("Nivel", 1.2), ("Detectada", 1.3)],
        vacio="No tiene dificultades vigentes.",
    )
    difs = grades.dificultades_visibles(user).filter(estudiante=est, estado=Dificultad.Estado.DETECTADA)
    for d in sorted(difs, key=lambda d: (d.tema.asignatura.nombre, d.promedio)):
        s_dif.filas.append([d.tema.asignatura.nombre, str(d.tema), d.promedio, d.get_nivel_display(), _fecha(d.detectada_en)])

    s_planes = Seccion(
        "Planes de refuerzo",
        [("Asignatura", 2.5), ("Estado", 1.3), ("Nivel", 1), ("Actividades cumplidas", 1.6),
         ("Avance %", 1), ("Temas superados", 1.4), ("Aprobado", 1.3)],
        vacio="No tiene planes de refuerzo.",
    )
    s_pend = Seccion(
        "Actividades de refuerzo pendientes",
        [("Asignatura", 2), ("Tema", 2.5), ("Fase ERCA", 1.6), ("Actividad", 4), ("Duración (min)", 1.2)],
        vacio="No tiene actividades de refuerzo pendientes.",
    )
    planes_ = refuerzo.planes_visibles(user).filter(estudiante=est)
    for p in sorted(planes_, key=lambda p: p.created_at, reverse=True):
        cumplidas, total, pct, superados, n_temas = _avance_plan(p)
        s_planes.filas.append([
            p.asignatura.nombre, p.get_estado_display(), p.get_nivel_display(), f"{cumplidas}/{total}", pct,
            f"{superados}/{n_temas}", _fecha(p.aprobado_en),
        ])
        if p.estado == PlanRefuerzo.Estado.APROBADA:
            for t in p.temas.all():
                for a in t.actividades.all():
                    if a.estado == ActividadRefuerzo.Estado.PENDIENTE:
                        s_pend.filas.append([
                            p.asignatura.nombre, str(t.tema), a.get_fase_display(), a.titulo, a.duracion_minutos or "",
                        ])
    return [s_asig, s_tema, s_dif, s_planes, s_pend]


def resumen(user, f):
    asignaciones = (
        academic.asignaciones_visibles(user).filter(is_active=True, paralelo__is_active=True)
        .order_by("paralelo__grado__orden", "paralelo__nombre", "asignatura__nombre")
    )
    notas_por = defaultdict(list)
    for c in grades.calificaciones_visibles(user).filter(estudiante__is_active=True).values_list(
        "actividad__asignacion_id", "valor"
    ):
        notas_por[c[0]].append(c[1])
    estudiantes_por = dict(
        academic.estudiantes_visibles(user).filter(is_active=True)
        .values("paralelo_id").annotate(n=Count("id")).values_list("paralelo_id", "n")
    )
    actividades_por = dict(
        Actividad.objects.filter(asignacion__in=asignaciones).exclude(estado=Actividad.Estado.CANCELADA)
        .values("asignacion_id").annotate(n=Count("id")).values_list("asignacion_id", "n")
    )
    detectadas = grades.dificultades_visibles(user).filter(
        estado=Dificultad.Estado.DETECTADA, estudiante__is_active=True
    )
    difs = defaultdict(set)
    for est, par, asig in detectadas.values_list("estudiante_id", "estudiante__paralelo_id", "tema__asignatura_id"):
        difs[(par, asig)].add(est)
    planes_por = defaultdict(lambda: defaultdict(int))
    for par, asig, estado in refuerzo.planes_base(user).filter(estudiante__is_active=True).values_list(
        "estudiante__paralelo_id", "asignatura_id", "estado"
    ):
        planes_por[(par, asig)][estado] += 1

    E = PlanRefuerzo.Estado
    tabla = Seccion(
        "Por paralelo y asignatura",
        [("Paralelo", 2), ("Asignatura", 2.2), ("Docente", 2.4), ("Estudiantes", 1.1), ("Actividades", 1.1),
         ("Notas", 1), ("Promedio", 1), ("Nivel de logro", 2.6), ("Con dificultad", 1.2),
         ("Planes vigentes", 1.2), ("Planes completados", 1.3)],
    )
    tot = defaultdict(int)
    for a in asignaciones:
        clave = (a.paralelo_id, a.asignatura_id)
        prom = scale.promedio(notas_por[a.id])
        vigentes = planes_por[clave][E.PROPUESTA] + planes_por[clave][E.APROBADA]
        fila = [
            a.paralelo.nombre_completo, a.asignatura.nombre, a.docente.full_name,
            estudiantes_por.get(a.paralelo_id, 0), actividades_por.get(a.id, 0), len(notas_por[a.id]),
            prom if prom is not None else "", _nivel(prom), len(difs[clave]), vigentes, planes_por[clave][E.COMPLETADA],
        ]
        tabla.filas.append(fila)
        for k, v in zip(("act", "notas", "dif", "vig", "comp"), (fila[4], fila[5], fila[8], fila[9], fila[10])):
            tot[k] += v

    todas = [v for vals in notas_por.values() for v in vals]
    prom_general = scale.promedio(todas)
    totales = Seccion(
        "Totales",
        [("Indicador", 4), ("Valor", 2)],
    )
    totales.filas = [
        ["Estudiantes activos", sum(estudiantes_por.values())],
        ["Actividades publicadas", tot["act"]],
        ["Notas registradas", tot["notas"]],
        ["Promedio general", prom_general if prom_general is not None else ""],
        ["Nivel de logro general", _nivel(prom_general)],
        ["Estudiantes con al menos una dificultad", detectadas.values("estudiante").distinct().count()],
        ["Planes vigentes (propuestos o aprobados)", tot["vig"]],
        ["Planes completados", tot["comp"]],
    ]

    top = Seccion(
        "Temas con más dificultades",
        [("Grado", 2), ("Asignatura", 2.4), ("Tema", 3.4), ("Estudiantes", 1.2), ("Promedio de esos estudiantes", 1.8)],
        vacio="No hay dificultades detectadas.",
    )
    ranking = (
        detectadas.values("tema_id").annotate(n=Count("estudiante", distinct=True)).order_by("-n")[:10]
    )
    ranking = list(ranking)
    temas = {
        t.id: t for t in Tema.objects.filter(id__in=[r["tema_id"] for r in ranking])
        .select_related("grado", "asignatura", "padre")
    }
    for r in ranking:
        t = temas[r["tema_id"]]
        valores = detectadas.filter(tema_id=t.id).values_list("promedio", flat=True)
        top.filas.append([t.grado.nombre, t.asignatura.nombre, str(t), r["n"], scale.promedio(valores)])

    return [totales, tabla, top]


CONSTRUCTORES = {
    "resumen": resumen,
    "calificaciones": calificaciones,
    "dificultades": dificultades,
    "planes": planes,
    "avance": avance,
}


def construir(user, definicion, filtros, etiquetas):
    return Reporte(
        clave=definicion.clave,
        titulo=definicion.titulo,
        descripcion=definicion.descripcion,
        filtros=etiquetas,
        secciones=CONSTRUCTORES[definicion.clave](user, filtros),
        generado_por=user.full_name,
    )
