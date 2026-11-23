import { CLAVES_COMUNES } from './clavesComunes'

/**
 * Reglas de la contraseña nueva. Replican los validadores del backend
 * (AUTH_PASSWORD_VALIDATORS en settings.py y _validar_nueva en recuperacion.py), así lo que
 * se marca en verde es lo mismo que acepta el servidor. El servidor sigue siendo el que decide.
 */
export const MIN_CLAVE = 10
export const MAX_CLAVE = 128 // = MAX_CLAVE del backend

// Igual que UserAttributeSimilarityValidator de Django (max_similarity = 0.7, quick_ratio).
const MAX_SIMILITUD = 0.7

function quickRatio(a, b) {
    const conteo = new Map()
    for (const c of b) conteo.set(c, (conteo.get(c) ?? 0) + 1)
    let coincidencias = 0
    for (const c of a) {
        const n = conteo.get(c) ?? 0
        if (n > 0) {
            coincidencias += 1
            conteo.set(c, n - 1)
        }
    }
    return a.length + b.length ? (2 * coincidencias) / (a.length + b.length) : 1
}

function muyLarga(clave, parte) {
    // exceeds_maximum_length_ratio de Django: si la contraseña es 10 veces más larga, no se compara.
    return clave.length >= 10 * parte.length && parte.length < (MAX_SIMILITUD / 2) * clave.length
}

/** true si la contraseña se parece demasiado a alguno de los datos (correo, nombres, apellidos). */
export function pareceDatoPersonal(clave, datos) {
    const minuscula = clave.toLowerCase()
    for (const dato of datos) {
        if (!dato || typeof dato !== 'string') continue
        const valor = dato.toLowerCase()
        const partes = [...valor.split(/[^\p{L}\p{N}_]+/u), valor]
        for (const parte of partes) {
            if (muyLarga(minuscula, parte)) continue
            if (quickRatio(minuscula, parte) >= MAX_SIMILITUD) return true
        }
    }
    return false
}

/**
 * Evalúa la contraseña nueva. Devuelve la lista de reglas { clave, texto, ok } y si todas
 * se cumplen. `datos`: correo, nombres y apellidos del usuario (los que se conozcan).
 */
export function evaluarClave(nueva, { temporal = '', datos = [] } = {}) {
    const reglas = [
        { clave: 'largo', texto: `Entre ${MIN_CLAVE} y ${MAX_CLAVE} caracteres`, ok: nueva.length >= MIN_CLAVE && nueva.length <= MAX_CLAVE },
        { clave: 'numeros', texto: 'No tiene solo números', ok: nueva.length > 0 && !/^\d+$/.test(nueva) },
        { clave: 'comun', texto: 'No es una contraseña común (p. ej. «password123»)', ok: nueva.trim().length > 0 && !CLAVES_COMUNES.has(nueva.toLowerCase().trim()) },
        { clave: 'personal', texto: 'No se parece a tu correo ni a tu nombre', ok: nueva.length > 0 && !pareceDatoPersonal(nueva, datos) },
        { clave: 'temporal', texto: 'Es distinta de la contraseña temporal', ok: nueva.length > 0 && nueva !== temporal.trim() },
    ]
    return { reglas, valida: reglas.every((r) => r.ok) }
}
