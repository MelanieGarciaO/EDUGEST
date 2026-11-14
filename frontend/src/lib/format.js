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

/**
 * Escala cualitativa del Reglamento General a la LOEI (sobre 10). Es el mismo cálculo que
 * `grades/scale.py` en el backend, para poder mostrar el semáforo en tiempo real.
 */
export const ESCALA_LOEI = [
    { nivel: 'DOMINA', sigla: 'DAR', nombre: 'Domina los aprendizajes requeridos', rango: '9,00 – 10,00', tone: 'ok' },
    { nivel: 'ALCANZA', sigla: 'AAR', nombre: 'Alcanza los aprendizajes requeridos', rango: '7,00 – 8,99', tone: 'brand' },
    { nivel: 'PROXIMO', sigla: 'PAAR', nombre: 'Está próximo a alcanzar los aprendizajes requeridos', rango: '4,01 – 6,99', tone: 'warn' },
    { nivel: 'NO_ALCANZA', sigla: 'NAAR', nombre: 'No alcanza los aprendizajes requeridos', rango: '0,00 – 4,00', tone: 'danger' },
]
const POR_NIVEL = Object.fromEntries(ESCALA_LOEI.map((e) => [e.nivel, e]))

export const NOTA_TONE = Object.fromEntries(ESCALA_LOEI.map((e) => [e.nivel, e.tone]))
export const NOTA_SIGLA = Object.fromEntries(ESCALA_LOEI.map((e) => [e.nivel, e.sigla]))
export const NOTA_NOMBRE = Object.fromEntries(ESCALA_LOEI.map((e) => [e.nivel, e.nombre]))
export const NOTA_LABEL = {
    DOMINA: 'Domina',
    ALCANZA: 'Alcanza',
    PROXIMO: 'Próximo a alcanzar',
    NO_ALCANZA: 'No alcanza',
}

/** Nivel cualitativo de una nota (número 0–10). null si no hay nota. */
export function nivelNota(valor) {
    if (valor == null || Number.isNaN(Number(valor))) return null
    const v = Number(valor)
    if (v >= 9) return 'DOMINA'
    if (v >= 7) return 'ALCANZA'
    if (v > 4) return 'PROXIMO'
    return 'NO_ALCANZA'
}

export const infoNivel = (nivel) => POR_NIVEL[nivel] ?? null

/** Etiqueta de reincidencia: «Reincidente · 2.ª vez». */
export const reincidenciaLabel = (veces) => `Reincidente · ${veces}.ª vez`

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

/** Ciclo de aprendizaje ERCA (Minedec): orden en que se presentan las actividades del plan. */
export const FASES_ERCA = [
    { value: 'EXPERIENCIA', label: 'Experiencia', letra: 'E', descripcion: 'Parte de algo que el estudiante ya vive o conoce.' },
    { value: 'REFLEXION', label: 'Reflexión', letra: 'R', descripcion: 'Piensa sobre lo que hizo: qué entendió y dónde se equivocó.' },
    { value: 'CONCEPTUALIZACION', label: 'Conceptualización', letra: 'C', descripcion: 'Aprende o repasa el concepto y sus pasos.' },
    { value: 'APLICACION', label: 'Aplicación', letra: 'A', descripcion: 'Practica y usa lo aprendido en situaciones nuevas.' },
]
export const FASE_LABEL = Object.fromEntries(FASES_ERCA.map((f) => [f.value, f.label]))

/** Principios del Diseño Universal para el Aprendizaje (DUA) de cada tema del plan. */
export const PRINCIPIOS_DUA = [
    { campo: 'dua_implicacion', titulo: 'Implicación', familia: 'Para motivarlo', pregunta: '¿Cómo motivarlo y mantener su interés?' },
    { campo: 'dua_representacion', titulo: 'Representación', familia: 'Para explicarle', pregunta: '¿Cómo presentarle el contenido?' },
    { campo: 'dua_accion_expresion', titulo: 'Acción y expresión', familia: 'Para que demuestre lo aprendido', pregunta: '¿Cómo puede demostrar lo que aprendió?' },
]
export const DUA_ORIGEN_LABEL = { REGLAS: 'Sugerido por el sistema', IA: 'Sugerido con IA y revisado', DOCENTE: 'Escrito por el docente' }

/** Evaluación de refuerzo de un plan completado. */
export function evaluacionPlan(ev) {
    if (!ev) return null
    if (ev.estado === 'PENDIENTE') return { label: 'Pendiente de evaluación', tone: 'warn' }
    if (ev.estado === 'PARCIAL') return { label: `Evaluado ${ev.temas_evaluados} de ${ev.temas_total} temas`, tone: 'warn' }
    return ev.resultado === 'SUPERADO'
        ? { label: 'Refuerzo superado', tone: 'ok' }
        : { label: 'Refuerzo no superado', tone: 'danger' }
}
