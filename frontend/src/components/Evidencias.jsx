import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, FileAudio, ImageOff, Mic, PenLine, Square, Trash2, Upload } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { cx } from '../lib/cx'
import { Button } from './ui'

const MAX_EVIDENCIAS = 3
const MAX_SEGUNDOS_AUDIO = 180
const TEXTO_MIN = 10
const TEXTO_MAX = 1000

const TIPOS = [
    { value: 'FOTO', label: 'Foto', icono: Camera },
    { value: 'AUDIO', label: 'Audio', icono: Mic },
    { value: 'TEXTO', label: 'Texto', icono: PenLine },
]

/** Descarga privada (con el token): las evidencias no tienen URL pública. */
function useArchivoPrivado(evidencia) {
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
    return { url, error }
}

function BotonEliminar({ onEliminar, eliminando, className }) {
    if (!onEliminar) return null
    return (
        <button
            type="button"
            onClick={onEliminar}
            disabled={eliminando}
            className={cx('rounded-lg bg-white/90 p-1 text-danger-600 hover:bg-white', className)}
            aria-label="Eliminar evidencia"
        >
            <Trash2 className="size-4" aria-hidden="true" />
        </button>
    )
}

function Foto({ evidencia, onEliminar, eliminando }) {
    const { url, error } = useArchivoPrivado(evidencia)
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
                <BotonEliminar onEliminar={onEliminar} eliminando={eliminando} className="absolute top-1 right-1" />
            </div>
            {evidencia.comentario ? <figcaption className="mt-1 line-clamp-2 text-xs text-ink-700">{evidencia.comentario}</figcaption> : null}
        </figure>
    )
}

function Audio({ evidencia, onEliminar, eliminando }) {
    const { url, error } = useArchivoPrivado(evidencia)
    return (
        <figure className="w-full max-w-sm rounded-xl border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-700">
                    <FileAudio className="size-4" aria-hidden="true" />
                    Audio
                </span>
                <BotonEliminar onEliminar={onEliminar} eliminando={eliminando} />
            </div>
            {error ? (
                <p className="mt-2 text-xs text-ink-500">No se pudo cargar el audio.</p>
            ) : url ? (
                <audio controls preload="metadata" src={url} className="mt-2 w-full">
                    Tu navegador no puede reproducir este audio.
                </audio>
            ) : (
                <p className="mt-2 text-xs text-ink-500">Cargando…</p>
            )}
            {evidencia.comentario ? <figcaption className="mt-1 text-xs text-ink-700">{evidencia.comentario}</figcaption> : null}
        </figure>
    )
}

function Texto({ evidencia, onEliminar, eliminando }) {
    return (
        <figure className="w-full max-w-sm rounded-xl border border-line bg-white p-3">
            <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-700">
                    <PenLine className="size-4" aria-hidden="true" />
                    Texto
                </span>
                <BotonEliminar onEliminar={onEliminar} eliminando={eliminando} />
            </div>
            <blockquote className="mt-2 border-l-4 border-brand-200 pl-3 text-sm whitespace-pre-line text-ink-900">{evidencia.texto}</blockquote>
            {evidencia.comentario ? <figcaption className="mt-1 text-xs text-ink-500">{evidencia.comentario}</figcaption> : null}
        </figure>
    )
}

const VISTA = { FOTO: Foto, AUDIO: Audio, TEXTO: Texto }

/** Formato que el navegador sabe grabar (Chrome/Firefox: webm; Safari/iPhone: mp4). */
function formatoGrabacion() {
    if (typeof window === 'undefined' || !window.MediaRecorder || !navigator.mediaDevices?.getUserMedia) return null
    for (const tipo of ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']) {
        if (MediaRecorder.isTypeSupported?.(tipo)) return tipo
    }
    return ''
}

/** Graba un audio corto con el micrófono del celular o la computadora. */
function GrabadorAudio({ onListo, deshabilitado }) {
    const [estado, setEstado] = useState('inactivo') // inactivo | grabando
    const [segundos, setSegundos] = useState(0)
    const [error, setError] = useState('')
    const grabador = useRef(null)
    const reloj = useRef(null)
    const formato = formatoGrabacion()

    useEffect(() => () => {
        clearInterval(reloj.current)
        grabador.current?.stream?.getTracks().forEach((t) => t.stop())
    }, [])

    if (formato === null) return null

    async function empezar() {
        setError('')
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const rec = new MediaRecorder(stream, formato ? { mimeType: formato } : undefined)
            const partes = []
            rec.ondataavailable = (e) => e.data.size && partes.push(e.data)
            rec.onstop = () => {
                stream.getTracks().forEach((t) => t.stop())
                clearInterval(reloj.current)
                setEstado('inactivo')
                const tipo = rec.mimeType || formato || 'audio/webm'
                const extension = tipo.includes('mp4') ? 'm4a' : tipo.includes('ogg') ? 'ogg' : 'webm'
                onListo(new File(partes, `audio.${extension}`, { type: tipo.split(';')[0] }))
            }
            grabador.current = rec
            rec.start()
            setSegundos(0)
            setEstado('grabando')
            reloj.current = setInterval(() => {
                setSegundos((s) => {
                    if (s + 1 >= MAX_SEGUNDOS_AUDIO) rec.state === 'recording' && rec.stop()
                    return s + 1
                })
            }, 1000)
        } catch {
            setError('No se pudo usar el micrófono. Revisa el permiso del navegador o adjunta un archivo de audio.')
        }
    }

    const mmss = `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, '0')}`
    return (
        <>
            {estado === 'grabando' ? (
                <Button variant="danger" onClick={() => grabador.current?.stop()}>
                    <Square className="size-4" aria-hidden="true" />
                    {`Detener (${mmss})`}
                </Button>
            ) : (
                <Button variant="secondary" onClick={empezar} disabled={deshabilitado}>
                    <Mic className="size-4" aria-hidden="true" />
                    Grabar audio
                </Button>
            )}
            {error && <p className="basis-full text-sm font-medium text-danger-600">{error}</p>}
        </>
    )
}

/**
 * Evidencias de una actividad de refuerzo (mejora 14). DUA · acción y expresión: el
 * estudiante demuestra lo aprendido como pueda — foto del trabajo, audio explicándolo o texto.
 * - modo «ver»: docente (solo mira y escucha).
 * - modo «subir»: representante (sube y elimina las suyas mientras el plan está en curso).
 */
export default function Evidencias({ actividad, plan, modo }) {
    const { user } = useAuth()
    const qc = useQueryClient()
    const fotoRef = useRef(null)
    const audioRef = useRef(null)
    const [tipo, setTipo] = useState('FOTO')
    const [comentario, setComentario] = useState('')
    const [texto, setTexto] = useState('')
    // Grabación o archivo listo para escucharlo antes de subirlo: { archivo, url }.
    const [audio, setAudioState] = useState(null)
    const audioActual = useRef(null)
    const [error, setError] = useState('')
    const lista = actividad.evidencias ?? []
    const enCurso = plan.estado === 'APROBADA'
    const puedeSubir = modo === 'subir' && ['APROBADA', 'COMPLETADA'].includes(plan.estado) && lista.length < MAX_EVIDENCIAS

    const setAudio = (archivo) => {
        if (audioActual.current) URL.revokeObjectURL(audioActual.current.url)
        audioActual.current = archivo ? { archivo, url: URL.createObjectURL(archivo) } : null
        setAudioState(audioActual.current)
    }
    useEffect(() => () => audioActual.current && URL.revokeObjectURL(audioActual.current.url), [])

    const refrescar = () => {
        qc.invalidateQueries({ queryKey: ['plan'] })
        qc.invalidateQueries({ queryKey: ['planes'] })
    }

    const subir = useMutation({
        mutationFn: async ({ tipo: t, archivo }) => {
            const datos = new FormData()
            datos.append('tipo', t)
            if (archivo) datos.append('archivo', archivo)
            if (t === 'TEXTO') datos.append('texto', texto.trim())
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
            setTexto('')
            setAudio(null)
            refrescar()
        },
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setError(fields.archivo ?? fields.texto ?? fields.comentario ?? fields.tipo ?? message)
        },
        onSettled: () => {
            if (fotoRef.current) fotoRef.current.value = ''
            if (audioRef.current) audioRef.current.value = ''
        },
    })

    const eliminar = useMutation({
        mutationFn: async (id) => api.delete(`/reinforcement/evidencias/${id}/`),
        onSuccess: refrescar,
        onError: (e) => setError(parseApiError(e).message),
    })

    if (lista.length === 0 && !puedeSubir) return null

    const largoTexto = texto.trim().length
    const comentarioInput = (
        <input
            type="text"
            maxLength={300}
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            placeholder="Comentario (opcional)"
            aria-label="Comentario de la evidencia"
            className="min-h-10 min-w-0 flex-1 basis-48 rounded-xl border border-line bg-white px-3 text-sm"
        />
    )

    return (
        <div className="mt-3 rounded-xl bg-brand-50/60 p-3">
            <p className="text-xs font-bold text-ink-700">{`Evidencias (${lista.length}/${MAX_EVIDENCIAS})`}</p>
            {lista.length > 0 ? (
                <div className="mt-2 flex flex-wrap items-start gap-3">
                    {lista.map((ev) => {
                        const Vista = VISTA[ev.tipo] ?? Foto
                        return (
                            <Vista
                                key={ev.id}
                                evidencia={ev}
                                eliminando={eliminar.isPending}
                                onEliminar={modo === 'subir' && enCurso && ev.subida_por === user.id ? () => eliminar.mutate(ev.id) : null}
                            />
                        )
                    })}
                </div>
            ) : null}

            {puedeSubir ? (
                <div className="mt-3 space-y-2">
                    <p className="text-xs text-ink-500">
                        Puede demostrar lo que aprendió como prefiera: una foto del trabajo, un audio explicándolo con sus palabras o un texto corto.
                    </p>
                    <div role="radiogroup" aria-label="Tipo de evidencia" className="inline-flex rounded-xl border border-line bg-white p-1">
                        {TIPOS.map((t) => {
                            const Icono = t.icono
                            const activo = tipo === t.value
                            return (
                                <button
                                    key={t.value}
                                    type="button"
                                    role="radio"
                                    aria-checked={activo}
                                    onClick={() => {
                                        setTipo(t.value)
                                        setError('')
                                    }}
                                    className={cx(
                                        'inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-sm font-bold',
                                        activo ? 'bg-brand-600 text-white' : 'text-ink-700 hover:bg-brand-50',
                                    )}
                                >
                                    <Icono className="size-4" aria-hidden="true" />
                                    {t.label}
                                </button>
                            )
                        })}
                    </div>

                    {tipo === 'FOTO' && (
                        <>
                            <p className="text-xs text-ink-500">
                                Fotografía el trabajo (cuaderno, hoja, maqueta), no el rostro del estudiante. Se eliminan la ubicación y los datos de la cámara.
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                                {comentarioInput}
                                <Button variant="secondary" onClick={() => fotoRef.current?.click()} loading={subir.isPending}>
                                    <Camera className="size-4" aria-hidden="true" />
                                    Subir foto
                                </Button>
                                <input
                                    ref={fotoRef}
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp"
                                    className="sr-only"
                                    aria-label="Foto de la evidencia"
                                    onChange={(e) => e.target.files?.[0] && subir.mutate({ tipo: 'FOTO', archivo: e.target.files[0] })}
                                />
                            </div>
                        </>
                    )}

                    {tipo === 'AUDIO' && (
                        <>
                            <p className="text-xs text-ink-500">
                                Que el estudiante explique con su voz qué hizo y cómo lo resolvió (máximo 3 minutos). Evita decir nombres completos u otros datos personales.
                            </p>
                            {audio ? (
                                <div className="space-y-2">
                                    <audio controls src={audio.url} className="w-full max-w-sm">
                                        Tu navegador no puede reproducir este audio.
                                    </audio>
                                    <div className="flex flex-wrap items-center gap-2">
                                        {comentarioInput}
                                        <Button variant="secondary" onClick={() => setAudio(null)} disabled={subir.isPending}>
                                            Descartar
                                        </Button>
                                        <Button onClick={() => subir.mutate({ tipo: 'AUDIO', archivo: audio.archivo })} loading={subir.isPending}>
                                            <Upload className="size-4" aria-hidden="true" />
                                            Subir audio
                                        </Button>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-wrap items-center gap-2">
                                    <GrabadorAudio onListo={setAudio} deshabilitado={subir.isPending} />
                                    <Button variant="secondary" onClick={() => audioRef.current?.click()} disabled={subir.isPending}>
                                        <FileAudio className="size-4" aria-hidden="true" />
                                        Elegir archivo de audio
                                    </Button>
                                    <input
                                        ref={audioRef}
                                        type="file"
                                        accept="audio/*"
                                        className="sr-only"
                                        aria-label="Archivo de audio de la evidencia"
                                        onChange={(e) => e.target.files?.[0] && setAudio(e.target.files[0])}
                                    />
                                </div>
                            )}
                        </>
                    )}

                    {tipo === 'TEXTO' && (
                        <div className="space-y-2">
                            <textarea
                                value={texto}
                                onChange={(e) => setTexto(e.target.value)}
                                maxLength={TEXTO_MAX}
                                rows={4}
                                placeholder="¿Qué hizo y qué aprendió? Puede escribirlo el estudiante o la familia con sus palabras."
                                aria-label="Texto de la evidencia"
                                className="block w-full rounded-xl border border-line bg-white px-3 py-2 text-sm"
                            />
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="text-xs text-ink-500">{`${largoTexto}/${TEXTO_MAX} · mínimo ${TEXTO_MIN} caracteres`}</span>
                                <Button
                                    onClick={() => subir.mutate({ tipo: 'TEXTO' })}
                                    loading={subir.isPending}
                                    disabled={largoTexto < TEXTO_MIN}
                                >
                                    <PenLine className="size-4" aria-hidden="true" />
                                    Guardar texto
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            ) : null}
            {error ? <p className="mt-2 text-sm font-medium text-danger-600">{error}</p> : null}
        </div>
    )
}
