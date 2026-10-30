import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Image as ImageIcon, Paperclip, Smartphone, Trash2, Upload, Users } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { abrirArchivo, useEntregas } from '../lib/archivos'
import { Button, Chip, cx } from './ui'

const MAX_PDF_MB = 10
const kb = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)
const multipart = { headers: { 'Content-Type': 'multipart/form-data' } }

// ---------------------------------------------------------------------------- docente
/** Elección de la modalidad de entrega al crear o editar la actividad. */
export function ModalidadEntrega({ value, onChange }) {
    const opciones = [
        { valor: 'PRESENCIAL', titulo: 'Presencial', texto: 'El estudiante entrega en clase.', icono: Users },
        { valor: 'APP', titulo: 'Desde la app', texto: 'El representante sube fotos o PDF del trabajo.', icono: Smartphone },
    ]
    return (
        <fieldset>
            <legend className="mb-1.5 text-sm font-bold text-ink-700">Modalidad de entrega</legend>
            <div className="grid gap-3 sm:grid-cols-2">
                {opciones.map(({ valor, titulo, texto, icono: Icono }) => (
                    <label
                        key={valor}
                        className={cx(
                            'flex cursor-pointer gap-3 rounded-xl border p-3',
                            value === valor ? 'border-brand-600 bg-brand-50 ring-2 ring-brand-600/20' : 'border-line hover:border-ink-300',
                        )}
                    >
                        <input type="radio" name="modalidad_entrega" value={valor} checked={value === valor} onChange={() => onChange(valor)} className="sr-only" />
                        <Icono className="mt-0.5 size-5 shrink-0 text-brand-600" aria-hidden="true" />
                        <span>
                            <span className="block font-bold text-ink-900">{titulo}</span>
                            <span className="block text-sm text-ink-500">{texto}</span>
                        </span>
                    </label>
                ))}
            </div>
        </fieldset>
    )
}

/** Selección de PDF antes de publicar (se suben al crear la actividad). */
export function SelectorPdf({ archivos, onChange, max = 5 }) {
    const ref = useRef(null)
    const [error, setError] = useState('')

    function agregar(lista) {
        setError('')
        const nuevos = []
        for (const f of lista) {
            if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) setError(`«${f.name}» no es un PDF.`)
            else if (f.size > MAX_PDF_MB * 1024 * 1024) setError(`«${f.name}» supera los ${MAX_PDF_MB} MB.`)
            else nuevos.push(f)
        }
        const total = [...archivos, ...nuevos]
        if (total.length > max) setError(`Máximo ${max} PDF por actividad.`)
        onChange(total.slice(0, max))
    }

    return (
        <div>
            <p className="text-sm font-bold text-ink-700">Archivos PDF (opcional)</p>
            <p className="mb-2 text-sm text-ink-500">{`Instrucciones, rúbrica o taller. Hasta ${max} archivos de ${MAX_PDF_MB} MB.`}</p>
            {archivos.length > 0 ? (
                <ul className="mb-2 space-y-1.5">
                    {archivos.map((f, i) => (
                        <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm">
                            <span className="flex min-w-0 items-center gap-2">
                                <FileText className="size-4 shrink-0 text-danger-600" aria-hidden="true" />
                                <span className="truncate">{f.name}</span>
                                <span className="shrink-0 text-ink-500">{kb(f.size)}</span>
                            </span>
                            <button type="button" className="text-danger-600" onClick={() => onChange(archivos.filter((_, k) => k !== i))} aria-label={`Quitar ${f.name}`}>
                                <Trash2 className="size-4" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            ) : null}
            {archivos.length < max ? (
                <Button variant="secondary" onClick={() => ref.current?.click()}>
                    <Paperclip className="size-4" aria-hidden="true" />
                    Adjuntar PDF
                </Button>
            ) : null}
            <input ref={ref} type="file" accept="application/pdf,.pdf" multiple className="sr-only" aria-label="Archivos PDF" onChange={(e) => { agregar([...(e.target.files ?? [])]); e.target.value = '' }} />
            {error ? <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p> : null}
        </div>
    )
}

/** PDF de la actividad. El docente (editable) puede agregar o quitar; los demás, descargar. */
export function AdjuntosActividad({ actividad, editable = false }) {
    const qc = useQueryClient()
    const ref = useRef(null)
    const [error, setError] = useState('')
    const lista = actividad.adjuntos ?? []
    const refrescar = () => qc.invalidateQueries({ queryKey: ['actividades'] })

    const subir = useMutation({
        mutationFn: async (archivo) => {
            const datos = new FormData()
            datos.append('archivo', archivo)
            return api.post(`/activities/actividades/${actividad.id}/adjuntos/`, datos, multipart)
        },
        onMutate: () => setError(''),
        onSuccess: refrescar,
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setError(fields.archivo ?? message)
        },
        onSettled: () => {
            if (ref.current) ref.current.value = ''
        },
    })
    const eliminar = useMutation({
        mutationFn: (id) => api.delete(`/activities/adjuntos/${id}/`),
        onSuccess: refrescar,
        onError: (e) => setError(parseApiError(e).message),
    })

    if (!lista.length && !editable) return null
    return (
        <div className="mt-3">
            <p className="mb-1.5 text-sm font-bold text-ink-700">Archivos de la actividad</p>
            <div className="flex flex-wrap gap-2">
                {lista.map((a) => (
                    <span key={a.id} className="inline-flex items-center gap-1 rounded-xl border border-line bg-white">
                        <button type="button" onClick={() => abrirArchivo(`/activities/adjuntos/${a.id}/archivo/`)} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-brand-700 hover:underline">
                            <FileText className="size-4 text-danger-600" aria-hidden="true" />
                            {a.nombre}
                            <span className="font-normal text-ink-500">{kb(a.tamano)}</span>
                        </button>
                        {editable ? (
                            <button type="button" className="pr-2 text-danger-600" disabled={eliminar.isPending} onClick={() => eliminar.mutate(a.id)} aria-label={`Eliminar ${a.nombre}`}>
                                <Trash2 className="size-4" aria-hidden="true" />
                            </button>
                        ) : null}
                    </span>
                ))}
                {editable && lista.length < 5 ? (
                    <Button variant="secondary" className="min-h-9" onClick={() => ref.current?.click()} loading={subir.isPending}>
                        <Paperclip className="size-4" aria-hidden="true" />
                        Agregar PDF
                    </Button>
                ) : null}
            </div>
            <input ref={ref} type="file" accept="application/pdf,.pdf" className="sr-only" aria-label="Agregar PDF" onChange={(e) => e.target.files?.[0] && subir.mutate(e.target.files[0])} />
            {error ? <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p> : null}
        </div>
    )
}

function ArchivoChip({ archivo, onEliminar, eliminando }) {
    const Icono = archivo.tipo === 'PDF' ? FileText : ImageIcon
    return (
        <span className="inline-flex items-center gap-1 rounded-xl border border-line bg-white">
            <button type="button" onClick={() => abrirArchivo(`/activities/archivos-entrega/${archivo.id}/archivo/`)} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-brand-700 hover:underline" title={archivo.comentario || undefined}>
                <Icono className="size-4" aria-hidden="true" />
                {archivo.nombre}
            </button>
            {onEliminar ? (
                <button type="button" className="pr-2 text-danger-600" disabled={eliminando} onClick={onEliminar} aria-label={`Eliminar ${archivo.nombre}`}>
                    <Trash2 className="size-4" aria-hidden="true" />
                </button>
            ) : null}
        </span>
    )
}

function EstadoEntrega({ fila }) {
    if (!fila.entregada) return <Chip tone="warn">Sin entrega</Chip>
    return (
        <>
            <Chip tone="ok">{`Entregada · ${fila.archivos.length} ${fila.archivos.length === 1 ? 'archivo' : 'archivos'}`}</Chip>
            {fila.tardia ? <Chip tone="danger">Fuera de plazo</Chip> : null}
        </>
    )
}

// ---------------------------------------------------------------------------- representante
/** Entrega desde la app (representante): fotos o PDF por cada estudiante suyo. */
export function EntregaRepresentante({ actividad }) {
    const { user } = useAuth()
    const qc = useQueryClient()
    const q = useEntregas(actividad.id, actividad.modalidad_entrega === 'APP')
    const [error, setError] = useState('')
    const [comentario, setComentario] = useState('')
    const ref = useRef(null)
    const [destino, setDestino] = useState(null) // estudiante al que se sube
    const refrescar = () => qc.invalidateQueries({ queryKey: ['entregas', actividad.id] })

    const subir = useMutation({
        mutationFn: async ({ archivo, estudiante }) => {
            const datos = new FormData()
            datos.append('archivo', archivo)
            datos.append('estudiante', String(estudiante))
            if (comentario.trim()) datos.append('comentario', comentario.trim())
            return api.post(`/activities/actividades/${actividad.id}/entregas/`, datos, multipart)
        },
        onMutate: () => setError(''),
        onSuccess: () => {
            setComentario('')
            refrescar()
        },
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setError(fields.archivo ?? fields.estudiante ?? fields.comentario ?? message)
        },
        onSettled: () => {
            if (ref.current) ref.current.value = ''
        },
    })
    const eliminar = useMutation({
        mutationFn: (id) => api.delete(`/activities/archivos-entrega/${id}/`),
        onSuccess: refrescar,
        onError: (e) => setError(parseApiError(e).message),
    })

    if (actividad.modalidad_entrega !== 'APP' || actividad.vigencia === 'cancelada') return null
    if (q.isPending) return <p className="mt-4 text-sm text-ink-500">Cargando la entrega…</p>
    if (q.isError) return null
    const { entregas, maximo_archivos: max } = q.data

    return (
        <div className="mt-4 rounded-xl border border-brand-100 bg-brand-50/60 p-4">
            <p className="flex items-center gap-2 font-bold text-navy-800">
                <Smartphone className="size-4 text-brand-600" aria-hidden="true" />
                Entrega desde la app
            </p>
            <p className="text-sm text-ink-500">Sube fotos (JPG, PNG) o PDF del trabajo terminado. Fotografía el trabajo, no el rostro del estudiante.</p>
            {entregas.map((fila) => {
                const abierta = !fila.calificada && fila.archivos.length < max
                return (
                    <div key={fila.estudiante} className="mt-3 border-t border-brand-100 pt-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-ink-900">{fila.estudiante_nombre}</span>
                            <EstadoEntrega fila={fila} />
                            {fila.calificada ? <Chip>Calificada: entrega cerrada</Chip> : null}
                        </div>
                        {fila.archivos.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-2">
                                {fila.archivos.map((a) => (
                                    <ArchivoChip key={a.id} archivo={a} eliminando={eliminar.isPending} onEliminar={!fila.calificada && a.subido_por === user.id ? () => eliminar.mutate(a.id) : null} />
                                ))}
                            </div>
                        ) : null}
                        {abierta ? (
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                                <input type="text" maxLength={300} value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Comentario (opcional)" aria-label="Comentario de la entrega" className="min-h-10 min-w-0 flex-1 basis-48 rounded-xl border border-line bg-white px-3 text-sm" />
                                <Button variant="secondary" loading={subir.isPending && destino === fila.estudiante} onClick={() => { setDestino(fila.estudiante); ref.current?.click() }}>
                                    <Upload className="size-4" aria-hidden="true" />
                                    {`Subir archivo (${fila.archivos.length}/${max})`}
                                </Button>
                            </div>
                        ) : null}
                    </div>
                )
            })}
            <input ref={ref} type="file" accept="image/jpeg,image/png,image/webp,application/pdf,.pdf" className="sr-only" aria-label="Archivo de la entrega" onChange={(e) => e.target.files?.[0] && destino && subir.mutate({ archivo: e.target.files[0], estudiante: destino })} />
            {error ? <p className="mt-2 text-sm font-medium text-danger-600">{error}</p> : null}
        </div>
    )
}

// ---------------------------------------------------------------------------- docente (Calificar)
/** Estado y archivos de la entrega de un estudiante (fila de Calificar). */
export function EntregaEstudiante({ fila }) {
    if (!fila) return null
    return (
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <EstadoEntrega fila={fila} />
            {fila.archivos.map((a) => (
                <ArchivoChip key={a.id} archivo={a} />
            ))}
        </div>
    )
}
