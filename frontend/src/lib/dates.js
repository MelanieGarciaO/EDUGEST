const pad = (n) => String(n).padStart(2, '0')

/** Convierte 'AAAA-MM-DD' en una fecha local (sin desfase de zona horaria). */
export function parseFecha(iso) {
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d)
}

export function hoyISO() {
    const d = new Date()
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** «Viernes 17 de octubre» */
export function formatFecha(iso) {
    const texto = new Intl.DateTimeFormat('es-EC', { weekday: 'long', day: 'numeric', month: 'long' }).format(parseFecha(iso))
    return texto.charAt(0).toUpperCase() + texto.slice(1)
}

export function diasRestantes(iso) {
    return Math.round((parseFecha(iso) - parseFecha(hoyISO())) / 86_400_000)
}

/** Texto del plazo: «Vence hoy», «Faltan 3 días», «Venció hace 2 días». */
export function textoPlazo(iso) {
    const n = diasRestantes(iso)
    if (n === 0) return 'Vence hoy'
    if (n === 1) return 'Vence mañana'
    if (n > 1) return `Faltan ${n} días`
    if (n === -1) return 'Venció ayer'
    return `Venció hace ${-n} días`
}

/** «14:30:00» → «14:30». Vacío si no hay hora fijada («00:00:00» significa sin hora específica). */
export function horaCorta(hhmmss) {
    if (!hhmmss || hhmmss.startsWith('00:00')) return ''
    return hhmmss.slice(0, 5)
}
