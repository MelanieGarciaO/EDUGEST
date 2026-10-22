/** Texto completo de un tema: «Quinto EGB · Matemática · Fracciones › Suma». */
export function temaLabel(t) {
    const nombre = t.padre_nombre ? `${t.padre_nombre} › ${t.nombre}` : t.nombre
    return `${t.grado_nombre} · ${t.asignatura_nombre} · ${nombre}`
}

export const NIVELES = [
    { value: 'BASICO', label: 'Básico' },
    { value: 'INTERMEDIO', label: 'Intermedio' },
    { value: 'AVANZADO', label: 'Avanzado' },
]

export const NIVEL_LABEL = Object.fromEntries(NIVELES.map((n) => [n.value, n.label]))
export const NIVEL_TONE = { BASICO: 'ok', INTERMEDIO: 'brand', AVANZADO: 'warn' }

/** Nivel cualitativo de una nota (escala LOEI sobre 10). */
export const NOTA_TONE = { DOMINA: 'ok', ALCANZA: 'brand', PROXIMO: 'warn', NO_ALCANZA: 'danger' }
export const NOTA_LABEL = {
    DOMINA: 'Domina',
    ALCANZA: 'Alcanza',
    PROXIMO: 'Próximo a alcanzar',
    NO_ALCANZA: 'No alcanza',
}

/** Formatea una nota «8.5» como «8,50». */
export const formatNota = (v) => (v == null ? '' : Number(v).toFixed(2).replace('.', ','))

/** Planes de refuerzo. */
export const PLAN_ESTADO_LABEL = { PROPUESTA: 'Propuesta', APROBADA: 'Aprobado', COMPLETADA: 'Completado', CANCELADA: 'Cancelado' }
export const PLAN_ESTADO_TONE = { PROPUESTA: 'warn', APROBADA: 'brand', COMPLETADA: 'ok', CANCELADA: 'danger' }
export const PLAN_NIVEL_LABEL = { REGULAR: 'Refuerzo regular', ALTO: 'Refuerzo alto' }

/** Estrategias de refuerzo académico (LOEI). */
export const ESTRATEGIAS = [
    { value: 'INDIVIDUAL', label: 'Trabajo individualizado' },
    { value: 'GRUPAL', label: 'Trabajo grupal' },
    { value: 'ENTRE_IGUALES', label: 'Ayuda entre iguales' },
    { value: 'TECNOLOGIA', label: 'Uso de tecnología' },
    { value: 'COOPERATIVO', label: 'Aprendizaje cooperativo' },
    { value: 'TAREA_CASA', label: 'Tareas para la casa' },
]
export const ESTRATEGIA_LABEL = Object.fromEntries(ESTRATEGIAS.map((e) => [e.value, e.label]))

/** Evaluación de refuerzo de un plan completado. */
export function evaluacionPlan(ev) {
    if (!ev) return null
    if (ev.estado === 'PENDIENTE') return { label: 'Pendiente de evaluación', tone: 'warn' }
    if (ev.estado === 'PARCIAL') return { label: `Evaluado ${ev.temas_evaluados} de ${ev.temas_total} temas`, tone: 'warn' }
    return ev.resultado === 'SUPERADO'
        ? { label: 'Refuerzo superado', tone: 'ok' }
        : { label: 'Refuerzo no superado', tone: 'danger' }
}
