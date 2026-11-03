import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

/** Abre un archivo privado: se pide a la API con el token y se muestra en otra pestaña. */
export async function abrirArchivo(ruta) {
    const ventana = window.open('', '_blank')
    try {
        const res = await api.get(ruta, { responseType: 'blob' })
        const url = URL.createObjectURL(res.data)
        if (ventana) ventana.location.href = url
        else window.location.href = url
        setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
        ventana?.close()
        window.alert('No se pudo abrir el archivo.')
    }
}

/** Estado de la entrega desde la app por estudiante (solo actividades con modalidad APP). */
export const useEntregas = (actividadId, enabled = true) =>
    useQuery({
        queryKey: ['entregas', actividadId],
        queryFn: async () => (await api.get(`/activities/actividades/${actividadId}/entregas/`)).data,
        enabled,
    })

/** Entregas del paralelo (docente). Devuelve un mapa estudiante -> fila para pintarlo en la lista. */
export function useEntregasPorEstudiante(actividad) {
    const q = useEntregas(actividad?.id, actividad?.modalidad_entrega === 'APP')
    const mapa = Object.fromEntries((q.data?.entregas ?? []).map((f) => [f.estudiante, f]))
    const entregadas = q.data?.entregas.filter((f) => f.entregada).length ?? 0
    return { mapa, entregadas, total: q.data?.entregas.length ?? 0, cargando: q.isPending && actividad?.modalidad_entrega === 'APP' }
}
