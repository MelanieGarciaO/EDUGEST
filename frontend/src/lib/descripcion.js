/**
 * Da estructura a la descripción de una actividad para mostrarla (no cambia lo guardado).
 *
 * - Si el docente escribió con saltos de línea, se respetan.
 * - Si el texto llegó en un solo bloque (actividades antiguas o pegadas desde un PDF), se
 *   reconstruyen las líneas antes de: títulos de sección («Objetivo», «Indicaciones…»,
 *   «Parte 2.»), campos de encabezado («Nombre:», «Fecha:»), ítems numerados («1. Lee», «2)»)
 *   e ítems con letra («a)», «b)»).
 *
 * Cada línea se clasifica para darle sangría: encabezado | titulo | parte | numero | letra | texto.
 */

const MAYUS = 'A-ZÁÉÍÓÚÑ¿¡'

// Títulos de sección habituales en guías y hojas de trabajo.
const TITULOS = [
    'Objetivos?',
    'Indicaciones(?: (?:para|del?) (?:el |la |los )?estudiantes?)?',
    'Instrucciones(?: (?:para|del?) (?:el |la |los )?estudiantes?)?',
    'Recordemos',
    'Recuerda',
    'Ejemplos?',
    'Desarrollo',
    'Actividades',
    'Evaluación',
    'Criterios de evaluación',
    'Autoevaluación',
    'Mi comprobación',
    'Conclusión',
    'Entrega',
    'Nota',
    'Observaciones?',
]
const RE_TITULO_LINEA = new RegExp(`^(${TITULOS.join('|')})(?::\\s*|\\s+(?=[${MAYUS}0-9])|$)`)
const RE_PARTE_LINEA = /^((?:Parte|Sección|Ejercicio|Actividad)\s+(?:\d{1,2}|[IVX]{1,4})\s*[.:)-]?)\s*/
const RE_NUMERO_LINEA = /^(\d{1,2}[.)])\s+/
const RE_LETRA_LINEA = /^([a-hA-H][.)])\s+/

// Puntos de corte para un texto en un solo bloque (se inserta un salto antes de cada uno).
// No cortar justo después de «Parte 1.» (ni separar el número de «Parte»).
const TRAS_PARTE = '(?<!(?:Parte|Sección|Ejercicio))(?<!(?:Parte|Sección|Ejercicio)\\s+(?:\\d{1,2}|[IVX]{1,4})\\s*[.:)]?)'

const CORTES = [
    // Títulos de sección seguidos de mayúscula, número o dos puntos.
    new RegExp(`${TRAS_PARTE} (?=(?:${TITULOS.join('|')})(?::| (?=[${MAYUS}0-9])))`, 'g'),
    // Parte 1. / Sección II / Ejercicio 3:
    / (?=(?:Parte|Sección|Ejercicio)\s+(?:\d{1,2}|[IVX]{1,4})\s*[.:)])/g,
    // Campos de encabezado de una hoja: Nombre: ____ Fecha: ____
    / (?=(?:Nombre|Fecha|Curso(?:\/paralelo)?|Paralelo|Grado|Asignatura|Docente|Estudiante):)/g,
    // Ítems numerados: «1. Lee…» (seguido de mayúscula) o «1) …».
    new RegExp(`${TRAS_PARTE} (?=\\d{1,2}\\.\\s+[${MAYUS}])`, 'g'),
    new RegExp(`${TRAS_PARTE} (?=\\d{1,2}\\)\\s)`, 'g'),
    // Ítems con letra: «a) 6/8». En columnas para unir («1) 1/3 a) 6/8») la pareja queda junta.
    /(?<!\d\)\s\S+) (?=[a-h]\)\s)/g,
]

function reconstruirLineas(texto) {
    let t = texto
    for (const re of CORTES) t = t.replace(re, '\n')
    return t
}

function clasificar(linea) {
    // Encabezado en mayúsculas: «ACTIVIDAD DE REFUERZO · Séptimo EGBM · …»
    const primera = linea.split(/\s[·|–-]\s/)[0]
    if (primera.length > 3 && /[A-ZÁÉÍÓÚÑ]{3}/.test(primera) && primera === primera.toUpperCase()) {
        return { tipo: 'encabezado', texto: linea }
    }
    let m = linea.match(RE_PARTE_LINEA)
    if (m) return { tipo: 'parte', etiqueta: m[1].replace(/\s*[.:)-]$/, ''), texto: linea.slice(m[0].length) }
    m = linea.match(RE_TITULO_LINEA)
    if (m) return { tipo: 'titulo', etiqueta: m[1], texto: linea.slice(m[0].length) }
    m = linea.match(RE_NUMERO_LINEA)
    if (m) return { tipo: 'numero', etiqueta: m[1], texto: linea.slice(m[0].length) }
    m = linea.match(RE_LETRA_LINEA)
    if (m) return { tipo: 'letra', etiqueta: m[1], texto: linea.slice(m[0].length) }
    return { tipo: 'texto', texto: linea }
}

/** Devuelve [{tipo, etiqueta?, texto}] listo para pintar. */
export function estructurarDescripcion(texto) {
    const limpio = (texto ?? '').replace(/\r\n?/g, '\n').trim()
    if (!limpio) return []
    const base = limpio.includes('\n') ? limpio : reconstruirLineas(limpio)
    const lineas = []
    for (const cruda of base.split('\n')) {
        const linea = cruda.replace(/[ \t]+/g, ' ').trim()
        if (!linea) {
            if (lineas.length && lineas[lineas.length - 1].tipo !== 'espacio') lineas.push({ tipo: 'espacio' })
            continue
        }
        lineas.push(clasificar(linea))
    }
    return lineas
}
