import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, ImageOff, Trash2 } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Button } from './ui'

const MAX_FOTOS = 3

/** Miniatura privada: la foto se pide a la API con el token (no hay URL pública). */
function Miniatura({ evidencia, onEliminar, eliminando }) {
    const [url, setUrl] = useState(null)
    const [error, setError] = useState(false)

    useEffect(() => {
        let vigente = true
        let objeto = null
        api.get(`/reinforcement/evidencias/${evidencia.id}/archivo/`, { responseType: 'blob' })
            .then((res) => {
                objeto = URL.createObjectURL(res.data)
                if (vigente) setUrl(objeto)
            })
            .catch(() => vigente && setError(true))
        return () => {
            vigente = false
            if (objeto) URL.revokeObjectURL(objeto)
        }
    }, [evidencia.id])

    return (
        <figure className="w-32">
            <div className="relative grid size-32 place-items-center overflow-hidden rounded-xl border border-line bg-brand-50">
                {error ? (
                    <ImageOff className="size-6 text-ink-300" aria-label="No se pudo cargar la foto" />
                ) : url ? (
                    <a href={url} target="_blank" rel="noreferrer" title="Ver en grande">
                        <img src={url} alt={evidencia.comentario || 'Evidencia de la actividad'} className="size-32 object-cover" />
                    </a>
                ) : (
                    <span className="text-xs text-ink-500">Cargando…</span>
                )}
                {onEliminar ? (
                    <button
                        type="button"
                        onClick={onEliminar}
                        disabled={eliminando}
                        className="absolute top-1 right-1 rounded-lg bg-white/90 p-1 text-danger-600 hover:bg-white"
                        aria-label="Eliminar foto"
                    >
                        <Trash2 className="size-4" aria-hidden="true" />
                    </button>
                ) : null}
            </div>
            {evidencia.comentario ? <figcaption className="mt-1 line-clamp-2 text-xs text-ink-700">{evidencia.comentario}</figcaption> : null}
        </figure>
    )
}

/**
 * Evidencias fotográficas de una actividad de refuerzo (mejora 14).
 * - modo «ver»: docente (solo mira).
 * - modo «subir»: representante (sube y elimina sus fotos mientras el plan está en curso).
 */
export default function Evidencias({ actividad, plan, modo }) {
    const { user } = useAuth()
    const qc = useQueryClient()
    const archivoRef = useRef(null)
    const [comentario, setComentario] = useState('')
    const [error, setError] = useState('')
    const lista = actividad.evidencias ?? []
    const enCurso = plan.estado === 'APROBADA'
    const puedeSubir = modo === 'subir' && ['APROBADA', 'COMPLETADA'].includes(plan.estado) && lista.length < MAX_FOTOS

    const refrescar = () => {
        qc.invalidateQueries({ queryKey: ['plan'] })
        qc.invalidateQueries({ queryKey: ['planes'] })
    }

    const subir = useMutation({
        mutationFn: async (archivo) => {
            const datos = new FormData()
            datos.append('archivo', archivo)
            if (comentario.trim()) datos.append('comentario', comentario.trim())
            return (
                await api.post(`/reinforcement/actividades/${actividad.id}/evidencias/`, datos, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                })
            ).data
        },
        onMutate: () => setError(''),
        onSuccess: () => {
            setComentario('')
            refrescar()
        },
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setError(fields.archivo ?? fields.comentario ?? message)
        },
        onSettled: () => {
            if (archivoRef.current) archivoRef.current.value = ''
        },
    })

    const eliminar = useMutation({
        mutationFn: async (id) => api.delete(`/reinforcement/evidencias/${id}/`),
        onSuccess: refrescar,
        onError: (e) => setError(parseApiError(e).message),
    })

    if (lista.length === 0 && !puedeSubir) return null

    return (
        <div className="mt-3 rounded-xl bg-brand-50/60 p-3">
            <p className="text-xs font-bold text-ink-700">{`Evidencias (${lista.length}/${MAX_FOTOS})`}</p>
            {lista.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-3">
                    {lista.map((ev) => (
                        <Miniatura
                            key={ev.id}
                            evidencia={ev}
                            eliminando={eliminar.isPending}
                            onEliminar={modo === 'subir' && enCurso && ev.subida_por === user.id ? () => eliminar.mutate(ev.id) : null}
                        />
                    ))}
                </div>
            ) : null}
            {puedeSubir ? (
                <div className="mt-2 space-y-2">
                    <p className="text-xs text-ink-500">
                        Fotografía el trabajo (cuaderno, hoja, maqueta), no el rostro del estudiante. Se eliminan la ubicación y los datos de la cámara.
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                        <input
                            type="text"
                            maxLength={300}
                            value={comentario}
                            onChange={(e) => setComentario(e.target.value)}
                            placeholder="Comentario (opcional)"
                            aria-label="Comentario de la evidencia"
                            className="min-h-10 min-w-0 flex-1 basis-48 rounded-xl border border-line bg-white px-3 text-sm"
                        />
                        <Button variant="secondary" onClick={() => archivoRef.current?.click()} loading={subir.isPending}>
                            <Camera className="size-4" aria-hidden="true" />
                            Subir foto
                        </Button>
                        <input
                            ref={archivoRef}
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="sr-only"
                            aria-label="Foto de la evidencia"
                            onChange={(e) => e.target.files?.[0] && subir.mutate(e.target.files[0])}
                        />
                    </div>
                </div>
            ) : null}
            {error ? <p className="mt-2 text-sm font-medium text-danger-600">{error}</p> : null}
        </div>
    )
}
