/**
 * Estado global del sistema, independiente de React y de la sesión.
 *
 *   ok          → todo funciona.
 *   offline     → el navegador no tiene conexión a internet.
 *   down        → el servidor no responde o la base de datos está caída.
 *   maintenance → el backend está en modo mantenimiento (503 con code "maintenance").
 *
 * El cliente HTTP lo actualiza en cada respuesta y la capa visual (SystemStatusOverlay)
 * lo lee para mostrar la pantalla que corresponda.
 */
import { useSyncExternalStore } from 'react'
import axios from 'axios'

const OK = Object.freeze({ tipo: 'ok', mensaje: '', hasta: '' })
let estado = OK
const suscriptores = new Set()

function emitir() {
    suscriptores.forEach((fn) => fn())
}

export const systemStatus = {
    get: () => estado,
    set(nuevo) {
        const siguiente = nuevo.tipo === 'ok' ? OK : { mensaje: '', hasta: '', ...nuevo }
        if (
            siguiente.tipo === estado.tipo &&
            siguiente.mensaje === estado.mensaje &&
            siguiente.hasta === estado.hasta
        ) {
            return
        }
        estado = siguiente
        emitir()
    },
    subscribe(fn) {
        suscriptores.add(fn)
        return () => suscriptores.delete(fn)
    },
}

export function useSystemStatus() {
    return useSyncExternalStore(systemStatus.subscribe, systemStatus.get)
}

const sinInternet = () => typeof navigator !== 'undefined' && navigator.onLine === false

/**
 * Traduce un error de axios a un estado del sistema, o null si es un error "normal"
 * (validación, permisos, no encontrado…) que la pantalla debe mostrar por su cuenta.
 */
export function estadoDesdeError(error) {
    if (axios.isCancel(error) || error?.code === 'ERR_CANCELED') return null
    const { response } = error ?? {}
    if (!response) return { tipo: sinInternet() ? 'offline' : 'down' }
    const { status, data } = response
    if (status === 503 && data?.code === 'maintenance') {
        return { tipo: 'maintenance', mensaje: data.detail ?? '', hasta: data.hasta ?? '' }
    }
    // 503: base de datos caída. 502/504: el proxy no alcanza al backend.
    if ([502, 503, 504].includes(status)) return { tipo: 'down' }
    return null
}

/** True si el error se debe a que el sistema no está disponible (no a la petición en sí). */
export function esErrorDeSistema(error) {
    return estadoDesdeError(error) !== null
}
