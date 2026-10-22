import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

/** Datos públicos para la política de privacidad y los términos (configurados en el .env). */
export function useLegalInfo() {
    const query = useQuery({
        queryKey: ['legal'],
        queryFn: async () => (await api.get('/security/legal/')).data,
        staleTime: Infinity,
    })
    const d = query.data ?? {}
    return {
        ...query,
        version: d.version ?? '',
        vigenteDesde: d.vigente_desde ?? '',
        // Si la institución aún no configuró sus datos, el texto sigue siendo legible.
        institucion: d.institucion || 'la institución educativa',
        ciudad: d.ciudad || '',
        correo: d.correo_privacidad || '',
        plazo: d.plazo_conservacion || 'el tiempo que exija la normativa educativa ecuatoriana',
    }
}

export function fechaLegal(iso) {
    if (!iso) return ''
    const fecha = new Date(`${iso}T12:00:00`)
    if (Number.isNaN(fecha.getTime())) return iso
    return fecha.toLocaleDateString('es-EC', { day: 'numeric', month: 'long', year: 'numeric' })
}
