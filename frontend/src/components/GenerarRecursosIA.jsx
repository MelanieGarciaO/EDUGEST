import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ChevronDown, FileText, Lightbulb, Paperclip, RotateCcw, Sparkles, X } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { ESTRATEGIAS, FASES_ERCA, NIVELES, temaLabel } from '../lib/format'
import { Alert, Button, Chip, Field, Modal, SelectField, TextAreaField } from './ui'

const ENDPOINT = '/reinforcement/recursos/'

/** Validación local (la definitiva la hace el servidor). */
function validarIndicaciones(texto, config) {
    const t = texto.trim()
    if (!t) return ''
    if (t.length < config.min_indicaciones) return `Escribe al menos ${config.min_indicaciones} caracteres o deja el campo vacío.`
    if (t.length > config.max_indicaciones) return `Máximo ${config.max_indicaciones} caracteres.`
    if (/https?:\/\/|www\./i.test(t)) return 'No incluyas enlaces; la IA no consulta páginas web.'
    if (/[\w.+-]+@[\w-]+\.[\w.]+/.test(t)) return 'No incluyas correos electrónicos ni datos personales.'
    if (/\b\d{9,}\b/.test(t)) return 'No incluyas cédulas, teléfonos u otros números de identificación.'
    return ''
}

/** Material de clase del docente (diapositivas, guías, fotos) que la IA usa como referencia. */
function SelectorMaterial({ archivos, onChange, config, error }) {
    const ref = useRef(null)
    const [aviso, setAviso] = useState('')
    const { max_archivos: maxArchivos, max_mb: maxMb, extensiones } = config

    function agregar(e) {
        const nuevos = Array.from(e.target.files ?? [])
        e.target.value = ''
        setAviso('')
        const validos = []
        for (const f of nuevos) {
            const ext = `.${f.name.split('.').pop().toLowerCase()}`
            if (!extensiones.includes(ext)) {
                setAviso(`«${f.name}»: formato no admitido.`)
                continue
            }
            if (f.size > maxMb * 1024 * 1024) {
                setAviso(`«${f.name}» supera los ${maxMb} MB.`)
                continue
            }
            if (archivos.some((a) => a.name === f.name && a.size === f.size)) continue
            validos.push(f)
        }
        const total = [...archivos, ...validos]
        if (total.length > maxArchivos) setAviso(`Puedes adjuntar hasta ${maxArchivos} archivos.`)
        onChange(total.slice(0, maxArchivos))
    }

    return (
        <div>
            <p className="mb-1.5 text-sm font-bold text-ink-700">
                Material de clase <span className="font-normal text-ink-500">(opcional)</span>
            </p>
            <p className="mb-2 text-xs text-ink-500">
                {`Diapositivas, guías o fotos de la pizarra para que la IA se base en ellas. PDF, PPTX, DOCX, TXT o imágenes; hasta ${maxArchivos} archivos de ${maxMb} MB. No sube listas de estudiantes ni calificaciones.`}
            </p>
            <input ref={ref} type="file" multiple accept={extensiones.join(',')} className="hidden" onChange={agregar} />
            {archivos.length > 0 && (
                <ul className="mb-2 space-y-1.5">
                    {archivos.map((f) => (
                        <li key={`${f.name}-${f.size}`} className="flex items-center gap-2 rounded-lg border border-line bg-white px-3 py-1.5 text-sm">
                            <FileText className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
                            <span className="min-w-0 flex-1 truncate">{f.name}</span>
                            <span className="text-xs text-ink-500">{`${(f.size / 1024 / 1024).toFixed(1)} MB`}</span>
                            <button
                                type="button"
                                onClick={() => onChange(archivos.filter((a) => a !== f))}
                                aria-label={`Quitar ${f.name}`}
                                className="grid size-7 place-items-center rounded-md text-ink-500 hover:bg-danger-50 hover:text-danger-600"
                            >
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            {archivos.length < maxArchivos && (
                <Button variant="ghost" onClick={() => ref.current?.click()}>
                    <Paperclip className="size-4" aria-hidden="true" />
                    {archivos.length ? 'Agregar otro archivo' : 'Adjuntar material'}
                </Button>
            )}
            {(aviso || error) && <p className="mt-1 text-xs font-medium text-danger-600">{error || aviso}</p>}
        </div>
    )
}

function Propuesta({ p, onChange }) {
    const set = (k) => (e) => onChange({ ...p, [k]: k === 'incluir' ? e.target.checked : e.target.value })
    return (
        <div className={`rounded-xl border p-4 ${p.guardado ? 'border-ok-600 bg-ok-50' : p.incluir ? 'border-brand-200 bg-white' : 'border-line bg-brand-50/40 opacity-70'}`}>
            <div className="mb-3 flex items-center justify-between gap-3">
                {p.guardado ? (
                    <Chip tone="ok">Guardado en el banco</Chip>
                ) : (
                    <label className="inline-flex items-center gap-2 text-sm font-bold text-ink-700">
                        <input type="checkbox" checked={p.incluir} onChange={set('incluir')} className="size-4 accent-brand-600" />
                        Guardar esta propuesta
                    </label>
                )}
                <Chip>
                    <Sparkles className="mr-1 inline size-3" aria-hidden="true" />
                    IA
                </Chip>
            </div>
            <fieldset disabled={p.guardado} className="space-y-3">
                <Field label="Título" value={p.titulo} onChange={set('titulo')} maxLength={200} error={p.errores?.titulo} />
                <SelectField label="Fase del ciclo ERCA" value={p.fase ?? ''} onChange={set('fase')} error={p.errores?.fase}>
                    <option value="">Automática (según el nivel)</option>
                    {FASES_ERCA.map((f) => (
                        <option key={f.value} value={f.value}>{`${f.letra} · ${f.label}`}</option>
                    ))}
                </SelectField>
                <div className="grid gap-3 sm:grid-cols-[1fr_9rem]">
                    <SelectField label="Estrategia" value={p.estrategia} onChange={set('estrategia')} error={p.errores?.estrategia}>
                        {ESTRATEGIAS.map((e) => (
                            <option key={e.value} value={e.value}>
                                {e.label}
                            </option>
                        ))}
                    </SelectField>
                    <Field label="Duración (min)" type="number" min="1" max="240" value={p.duracion_minutos} onChange={set('duracion_minutos')} error={p.errores?.duracion_minutos} />
                </div>
                <TextAreaField label="Instrucciones" rows={6} value={p.instrucciones} onChange={set('instrucciones')} maxLength={2000} error={p.errores?.instrucciones} />
                {p.errorGeneral && <Alert>{p.errorGeneral}</Alert>}
            </fieldset>
        </div>
    )
}

export default function GenerarRecursosIA({ temas, config, onClose }) {
    const queryClient = useQueryClient()
    const [valores, setValores] = useState({ tema: '', nivel: '', estrategia: '', cantidad: '3', duracion_minutos: '', indicaciones: '' })
    const [errores, setErrores] = useState({})
    const [general, setGeneral] = useState('')
    const [cargando, setCargando] = useState('')
    const [resultado, setResultado] = useState(null) // { propuestas, advertencias }
    const [verConsejos, setVerConsejos] = useState(false)
    const [archivos, setArchivos] = useState([])
    const set = (k) => (e) => setValores((v) => ({ ...v, [k]: e.target.value }))

    async function generar() {
        const local = {}
        if (!valores.tema) local.tema = 'Elige el tema.'
        if (!valores.nivel) local.nivel = 'Elige el nivel.'
        const minutos = valores.duracion_minutos === '' ? null : Number(valores.duracion_minutos)
        if (minutos !== null && (!Number.isInteger(minutos) || minutos < 5 || minutos > 120)) local.duracion_minutos = 'Entre 5 y 120 minutos.'
        const errInd = validarIndicaciones(valores.indicaciones, config)
        if (errInd) local.indicaciones = errInd
        setErrores(local)
        setGeneral('')
        if (Object.keys(local).length) return

        setCargando('generar')
        try {
            // Con material se envía multipart (archivos); sin material, JSON.
            const campos = {
                tema: Number(valores.tema),
                nivel: valores.nivel,
                estrategia: valores.estrategia,
                cantidad: Number(valores.cantidad),
                indicaciones: valores.indicaciones.trim(),
                ...(minutos !== null ? { duracion_minutos: minutos } : {}),
            }
            let cuerpo = campos
            let opciones = { timeout: 180_000 } // mayor que IA_TIMEOUT_SEGUNDOS del backend
            if (archivos.length) {
                cuerpo = new FormData()
                Object.entries(campos).forEach(([k, v]) => cuerpo.append(k, String(v)))
                archivos.forEach((f) => cuerpo.append('materiales', f))
                opciones = { ...opciones, headers: { 'Content-Type': 'multipart/form-data' } }
            }
            const { data } = await api.post(`${ENDPOINT}generar-ia/`, cuerpo, opciones)
            setResultado({
                ...data,
                propuestas: data.propuestas.map((p, i) => ({ ...p, clave: `${Date.now()}-${i}`, incluir: true, guardado: false })),
            })
        } catch (err) {
            const { fields, message } = parseApiError(err)
            // Los errores de la IA (429, 502, 503) traen un motivo útil en «detail»; se muestra tal cual.
            const detalle = err?.response?.data?.detail
            setErrores(fields)
            setGeneral(Object.keys(fields).length ? '' : typeof detalle === 'string' ? detalle : message)
        } finally {
            setCargando('')
        }
    }

    async function guardar() {
        setCargando('guardar')
        const nuevas = [...resultado.propuestas]
        let guardadas = 0
        for (let i = 0; i < nuevas.length; i++) {
            const p = nuevas[i]
            if (!p.incluir || p.guardado) continue
            try {
                await api.post(ENDPOINT, {
                    tema: p.tema,
                    nivel: p.nivel,
                    estrategia: p.estrategia,
                    fase: p.fase ?? '',
                    titulo: p.titulo.trim(),
                    instrucciones: p.instrucciones.trim(),
                    duracion_minutos: p.duracion_minutos === '' ? null : Number(p.duracion_minutos),
                    generado_ia: true,
                })
                nuevas[i] = { ...p, guardado: true, errores: {}, errorGeneral: '' }
                guardadas++
            } catch (err) {
                const { fields, message } = parseApiError(err)
                nuevas[i] = { ...p, errores: fields, errorGeneral: Object.keys(fields).length ? '' : message }
            }
        }
        setResultado((r) => ({ ...r, propuestas: nuevas }))
        if (guardadas) queryClient.invalidateQueries({ queryKey: ['recursos'] })
        setCargando('')
    }

    const pendientes = resultado?.propuestas.filter((p) => p.incluir && !p.guardado).length ?? 0
    const todasGuardadas = resultado && resultado.propuestas.every((p) => p.guardado || !p.incluir) && resultado.propuestas.some((p) => p.guardado)
    const largo = valores.indicaciones.length

    return (
        <Modal
            open
            size="xl"
            onClose={() => !cargando && onClose()}
            title="Generar recursos con IA"
            footer={
                !resultado ? (
                    <>
                        <Button variant="secondary" onClick={onClose} disabled={!!cargando}>
                            Cancelar
                        </Button>
                        <Button onClick={generar} loading={cargando === 'generar'}>
                            <Sparkles className="size-4" aria-hidden="true" />
                            {cargando === 'generar' ? 'Generando… (puede tardar hasta 2 min)' : 'Generar propuestas'}
                        </Button>
                    </>
                ) : (
                    <>
                        <Button variant="secondary" onClick={() => setResultado(null)} disabled={!!cargando}>
                            <RotateCcw className="size-4" aria-hidden="true" />
                            Ajustar y volver a generar
                        </Button>
                        {todasGuardadas ? (
                            <Button onClick={onClose}>Listo</Button>
                        ) : (
                            <Button onClick={guardar} loading={cargando === 'guardar'} disabled={!pendientes}>
                                {`Guardar ${pendientes} en el banco`}
                            </Button>
                        )}
                    </>
                )
            }
        >
            {!resultado ? (
                <div className="space-y-4">
                    {general && <Alert>{general}</Alert>}
                    <SelectField label="Tema" value={valores.tema} onChange={set('tema')} error={errores.tema}>
                        <option value="">Elige un tema o subtema</option>
                        {temas.map((t) => (
                            <option key={t.id} value={t.id}>
                                {temaLabel(t)}
                            </option>
                        ))}
                    </SelectField>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <SelectField label="Nivel de dificultad" value={valores.nivel} onChange={set('nivel')} error={errores.nivel}>
                            <option value="">Elige un nivel</option>
                            {NIVELES.map((n) => (
                                <option key={n.value} value={n.value}>
                                    {n.label}
                                </option>
                            ))}
                        </SelectField>
                        <SelectField label="Estrategia" value={valores.estrategia} onChange={set('estrategia')} error={errores.estrategia}>
                            <option value="">Variada (la IA elige)</option>
                            {ESTRATEGIAS.map((e) => (
                                <option key={e.value} value={e.value}>
                                    {e.label}
                                </option>
                            ))}
                        </SelectField>
                        <SelectField label="Cantidad de propuestas" value={valores.cantidad} onChange={set('cantidad')} error={errores.cantidad}>
                            {Array.from({ length: config.max_recursos }, (_, i) => i + 1).map((n) => (
                                <option key={n} value={n}>
                                    {n}
                                </option>
                            ))}
                        </SelectField>
                        <Field
                            label="Duración por actividad (min)"
                            type="number"
                            min="5"
                            max="120"
                            value={valores.duracion_minutos}
                            onChange={set('duracion_minutos')}
                            error={errores.duracion_minutos}
                            hint="Opcional, entre 5 y 120."
                        />
                    </div>

                    <div>
                        <TextAreaField
                            label="Indicaciones para la IA (opcional)"
                            rows={4}
                            value={valores.indicaciones}
                            onChange={set('indicaciones')}
                            error={errores.indicaciones}
                            maxLength={config.max_indicaciones}
                            placeholder="Ej.: Actividades con material concreto para estudiantes que confunden numerador y denominador."
                        />
                        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-ink-500">
                            <button type="button" onClick={() => setVerConsejos((v) => !v)} className="inline-flex items-center gap-1 font-bold text-brand-700 hover:underline" aria-expanded={verConsejos}>
                                <Lightbulb className="size-3.5" aria-hidden="true" />
                                Consejos para escribir buenas indicaciones
                                <ChevronDown className={`size-3.5 transition ${verConsejos ? 'rotate-180' : ''}`} aria-hidden="true" />
                            </button>
                            <span className={largo > config.max_indicaciones ? 'text-danger-600' : ''}>{`${largo}/${config.max_indicaciones}`}</span>
                        </div>
                        {verConsejos && (
                            <div className="mt-2 space-y-3 rounded-xl bg-brand-50 p-4 text-sm text-ink-700">
                                <ul className="list-disc space-y-1 pl-5">
                                    {config.recomendaciones.map((r) => (
                                        <li key={r}>{r}</li>
                                    ))}
                                </ul>
                                <div>
                                    <p className="mb-1.5 text-xs font-bold text-ink-700">Ejemplos (toca para usarlos):</p>
                                    <div className="flex flex-wrap gap-2">
                                        {config.ejemplos.map((e) => (
                                            <button
                                                key={e}
                                                type="button"
                                                onClick={() => setValores((v) => ({ ...v, indicaciones: e }))}
                                                className="rounded-full border border-brand-200 bg-white px-3 py-1 text-left text-xs text-brand-700 hover:bg-brand-100"
                                            >
                                                {e}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                    {config.material && (
                        <SelectorMaterial archivos={archivos} onChange={setArchivos} config={config.material} error={errores.materiales} />
                    )}
                    <p className="text-xs text-ink-500">
                        La IA solo recibe la asignatura, el grado, el tema, tus indicaciones y el material que adjuntes (sin correos, cédulas ni teléfonos); nunca datos de estudiantes del sistema. Las propuestas no se guardan hasta que las revises.
                        {` Límite: ${config.limite_por_hora} generaciones por hora.`}
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {resultado.material && (
                        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-700">
                            <span className="font-bold">Basado en:</span>
                            {resultado.material.archivos.map((n) => (
                                <Chip key={n} tone={resultado.material.relacionado ? 'brand' : 'warn'}>
                                    {n}
                                </Chip>
                            ))}
                        </div>
                    )}
                    {resultado.advertencias.map((a) => (
                        <Alert key={a} tone="warn">
                            {a}
                        </Alert>
                    ))}
                    {resultado.modelo && <p className="text-xs text-ink-500">{`Modelo usado: ${resultado.modelo}`}</p>}
                    <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
                        {resultado.propuestas.map((p, i) => (
                            <Propuesta
                                key={p.clave}
                                p={p}
                                onChange={(nueva) => setResultado((r) => ({ ...r, propuestas: r.propuestas.map((x, j) => (j === i ? nueva : x)) }))}
                            />
                        ))}
                    </div>
                </div>
            )}
        </Modal>
    )
}
