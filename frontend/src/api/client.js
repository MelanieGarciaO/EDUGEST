import axios from 'axios'

import { esErrorDeSistema, estadoDesdeError, systemStatus } from './system'

const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api').replace(/\/$/, '')
const REFRESH_KEY = 'edugest.refresh'

// El token de acceso vive solo en memoria; el de refresco, en sessionStorage
// (se borra al cerrar la pestaña).
let accessToken = null
let sessionExpiredHandler = null

function readRefresh() {
    try {
        return sessionStorage.getItem(REFRESH_KEY)
    } catch {
        return null
    }
}

function writeRefresh(value) {
    try {
        if (value) sessionStorage.setItem(REFRESH_KEY, value)
        else sessionStorage.removeItem(REFRESH_KEY)
    } catch {
        // sessionStorage no disponible: la sesión durará solo hasta recargar la página.
    }
}

export const tokenStore = {
    getAccess: () => accessToken,
    getRefresh: readRefresh,
    set(access, refresh) {
        accessToken = access ?? null
        if (refresh !== undefined) writeRefresh(refresh)
    },
    clear() {
        accessToken = null
        writeRefresh(null)
    },
}

/** Registra la función que se ejecuta cuando la sesión ya no se puede renovar. */
export function onSessionExpired(handler) {
    sessionExpiredHandler = handler
}

export const api = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
})

// Cliente sin interceptores, solo para renovar el token (evita bucles).
const raw = axios.create({ baseURL: BASE_URL })

api.interceptors.request.use((config) => {
    if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
    return config
})

let refreshing = null

/** Renueva el token de acceso. Varias llamadas simultáneas comparten una sola petición. */
export function refreshAccess() {
    if (!refreshing) {
        const refresh = readRefresh()
        if (!refresh) return Promise.reject(new Error('Sin sesión'))
        refreshing = raw
            .post('/security/auth/refresh/', { refresh })
            .then(({ data }) => {
                tokenStore.set(data.access, data.refresh ?? refresh)
                return data.access
            })
            .finally(() => {
                refreshing = null
            })
    }
    return refreshing
}

const SIN_RENOVACION = ['/security/auth/login/', '/security/auth/refresh/', '/security/auth/logout/']

/** Consulta /health/ y actualiza el estado del sistema. Devuelve el tipo resultante. */
export async function checkHealth() {
    try {
        // Sin cabeceras extra: una cabecera personalizada (p. ej. Cache-Control) obliga al navegador
        // a hacer un preflight de CORS que el backend no permite. El parámetro evita la caché.
        await raw.get('/health/', { params: { _: Date.now() } })
        systemStatus.set({ tipo: 'ok' })
    } catch (error) {
        systemStatus.set(estadoDesdeError(error) ?? { tipo: 'down' })
    }
    return systemStatus.get().tipo
}

api.interceptors.response.use(
    (response) => {
        // Una respuesta correcta significa que el sistema volvió.
        if (systemStatus.get().tipo !== 'ok') systemStatus.set({ tipo: 'ok' })
        return response
    },
    async (error) => {
        const caida = estadoDesdeError(error)
        if (caida) {
            systemStatus.set(caida)
            return Promise.reject(error)
        }
        const { response, config } = error
        const url = config?.url ?? ''
        if (
            response?.status === 401 &&
            config &&
            !config._retry &&
            !SIN_RENOVACION.some((ruta) => url.includes(ruta))
        ) {
            config._retry = true
            try {
                const access = await refreshAccess()
                config.headers.Authorization = `Bearer ${access}`
                return api(config)
            } catch (refreshError) {
                // Si no se pudo renovar porque el servidor está caído, la sesión NO se cierra:
                // se muestra la pantalla de servicio no disponible y se reintenta al volver.
                if (esErrorDeSistema(refreshError)) {
                    systemStatus.set(estadoDesdeError(refreshError))
                    return Promise.reject(refreshError)
                }
                tokenStore.clear()
                sessionExpiredHandler?.()
            }
        }
        return Promise.reject(error)
    },
)

/**
 * Convierte un error de la API en un mensaje legible y, si el servidor devolvió
 * errores por campo (400), en un objeto { campo: mensaje }.
 */
export function parseApiError(error, fallback = 'Ocurrió un error inesperado. Inténtalo de nuevo.') {
    if (!error?.response) {
        return {
            message: 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.',
            fields: {},
            status: 0,
        }
    }
    const { status, data } = error.response
    if (status === 503 && data?.code === 'maintenance') {
        return { message: 'EduGest está en mantenimiento. Inténtalo más tarde.', fields: {}, status }
    }
    if (status === 429) {
        return { message: 'Demasiados intentos. Espera un minuto e inténtalo de nuevo.', fields: {}, status }
    }
    if (status >= 500) {
        return {
            message: 'El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.',
            fields: {},
            status,
        }
    }

    const texto = (valor) => (Array.isArray(valor) ? valor.join(' ') : String(valor))
    const fields = {}
    let message = ''

    if (data && typeof data === 'object') {
        for (const [clave, valor] of Object.entries(data)) {
            if (clave === 'detail') message = texto(valor)
            else if (clave === 'non_field_errors') message = message || texto(valor)
            else fields[clave] = texto(valor)
        }
    }
    if (!message) {
        const unidos = Object.values(fields).join(' ')
        message = unidos || fallback
    }
    return { message, fields, status }
}

/** Recorre todas las páginas de un listado paginado y devuelve los elementos. */
export async function fetchAll(url, params = {}) {
    const items = []
    for (let page = 1; page <= 50; page += 1) {
        const { data } = await api.get(url, { params: { ...params, page } })
        items.push(...data.results)
        if (!data.next) break
    }
    return items
}
