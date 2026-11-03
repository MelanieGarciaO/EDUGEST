import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Send, Sparkles } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { MaterialesInput } from '../../components/Materiales'
import { Alert, Button, Card, CheckboxField, Field, PageHeader, SelectField, TextAreaField } from '../../components/ui'
import { hoyISO } from '../../lib/dates'
import { useAsignaciones } from '../../lib/queries'
import { ModalidadEntrega, SelectorPdf } from '../../components/ArchivosActividad'

const MIN = 3
const MAX = 2000

/** Aviso bajo un campo según la confianza con la que se extrajo. */
function aviso(confianza, vacio) {
    if (vacio || !confianza) return 'No se detectó este dato. Complétalo.'
    if (confianza === 'baja') return 'Dato poco seguro. Revísalo antes de publicar.'
    if (confianza === 'media') return 'Confirma que este dato sea correcto.'
    return undefined
}

/**
 * Fallback manual: un campo va en amarillo si está vacío o el PLN lo extrajo con
 * confianza baja y el docente aún no lo ha cambiado. Al completarlo, el amarillo se quita.
 */
function requiereAtencion(valor, confianza, original) {
    if (!String(valor ?? '').trim()) return true
    return confianza === 'baja' && valor === original
}

export default function NuevaActividad() {
    const navigate = useNavigate()
    const qc = useQueryClient()
    const asignaciones = useAsignaciones()

    const [paralelo, setParalelo] = useState('')
    const [texto, setTexto] = useState('')
    const [prev, setPrev] = useState(null) // respuesta de previsualizar
    const [form, setForm] = useState(null)
    const [err, setErr] = useState({ message: '', fields: {} })
    const [pdfs, setPdfs] = useState([]) // PDF del docente: se suben tras publicar

    // Paralelos donde el docente tiene asignaciones activas (sin repetir).
    const paralelos = [...new Map((asignaciones.data ?? []).map((a) => [a.paralelo, a.paralelo_nombre])).entries()]
    const paraleloId = paralelo || (paralelos.length === 1 ? String(paralelos[0][0]) : '')

    const preview = useMutation({
        mutationFn: async () =>
            (await api.post('/activities/actividades/previsualizar/', { paralelo: Number(paraleloId), texto: texto.trim() })).data,
        onSuccess: (data) => {
            const p = data.propuesta
            setPrev(data)
            setForm({
                asignatura: p.asignatura ? String(p.asignatura) : '',
                descripcion: p.descripcion ?? '',
                fecha_entrega: p.fecha_entrega ? p.fecha_entrega.slice(0, 10) : '',
                hora_entrega: '',
                materiales: p.materiales ?? [],
                tema: p.tema ?? '',
                es_evaluacion_refuerzo: false,
                modalidad_entrega: 'PRESENCIAL',
            })
            setErr({ message: '', fields: {} })
        },
    })

    const publish = useMutation({
        mutationFn: async () => {
            const { data: actividad } = await api.post('/activities/actividades/', {
                paralelo: prev.paralelo,
                asignatura: Number(form.asignatura),
                descripcion: form.descripcion.trim(),
                fecha_entrega: form.fecha_entrega,
                hora_entrega: form.hora_entrega || null,
                materiales: form.materiales,
                tema: form.tema.trim(),
                es_evaluacion_refuerzo: form.es_evaluacion_refuerzo,
                modalidad_entrega: form.modalidad_entrega,
                extraccion: prev.extraccion,
            })
            // La actividad ya quedó publicada; los PDF se adjuntan uno a uno.
            const fallidos = []
            for (const archivo of pdfs) {
                const datos = new FormData()
                datos.append('archivo', archivo)
                try {
                    await api.post(`/activities/actividades/${actividad.id}/adjuntos/`, datos, { headers: { 'Content-Type': 'multipart/form-data' } })
                } catch (e) {
                    fallidos.push(`${archivo.name}: ${parseApiError(e).fields.archivo ?? parseApiError(e).message}`)
                }
            }
            return fallidos
        },
        onSuccess: (fallidos) => {
            qc.invalidateQueries({ queryKey: ['actividades'] })
            if (fallidos.length) window.alert(`La actividad se publicó, pero no se pudieron adjuntar:\n${fallidos.join('\n')}\n\nPuedes agregarlos desde la tarjeta de la actividad.`)
            navigate('/docente/actividades')
        },
        onError: (e) => setErr(parseApiError(e)),
    })

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
    const len = texto.trim().length
    const canPreview = !!paraleloId && len >= MIN && len <= MAX
    const previewError = preview.isError ? parseApiError(preview.error) : null

    const back = (
        <Link to="/docente/actividades" className="mb-4 inline-flex items-center gap-1.5 text-sm font-bold text-brand-700 hover:underline">
            <ArrowLeft className="size-4" aria-hidden="true" />
            Volver a actividades
        </Link>
    )

    // ---------- Paso 1: describir ----------
    if (!prev) {
        return (
            <>
                {back}
                <PageHeader title="Nueva actividad" subtitle="Escribe la tarea con tus palabras. Antes de publicar podrás revisar lo que entendimos." />
                <Card className="max-w-3xl space-y-5">
                    {previewError && <Alert>{previewError.fields.texto ?? previewError.fields.paralelo ?? previewError.message}</Alert>}
                    <SelectField label="Paralelo" value={paraleloId} onChange={(e) => setParalelo(e.target.value)}>
                        <option value="">Selecciona un paralelo</option>
                        {paralelos.map(([id, nombre]) => (
                            <option key={id} value={id}>{nombre}</option>
                        ))}
                    </SelectField>
                    {asignaciones.isSuccess && paralelos.length === 0 && (
                        <Alert tone="warn">No tienes paralelos asignados. Pide al administrador que te asigne uno.</Alert>
                    )}
                    <TextAreaField
                        label="Describe la actividad"
                        value={texto}
                        maxLength={MAX}
                        rows={6}
                        placeholder="Ej.: Matemática: resolver la página 45 del libro para el viernes 23 de octubre. Traer regla y compás."
                        onChange={(e) => setTexto(e.target.value)}
                        hint={`Indica materia, qué deben hacer, fecha de entrega y materiales. ${len}/${MAX}`}
                    />
                    <div className="flex justify-end">
                        <Button onClick={() => preview.mutate()} disabled={!canPreview} loading={preview.isPending}>
                            <Sparkles className="size-4" aria-hidden="true" />
                            Previsualizar
                        </Button>
                    </div>
                </Card>
            </>
        )
    }

    // ---------- Paso 2: revisar y publicar ----------
    const p = prev.propuesta
    const vacio = (k) => p.campos_vacios?.includes(k)
    const f = err.fields
    const atencion = {
        asignatura: requiereAtencion(form.asignatura, p.confianza?.asignatura, p.asignatura ? String(p.asignatura) : ''),
        descripcion: requiereAtencion(form.descripcion, p.confianza?.descripcion, p.descripcion ?? ''),
        fecha_entrega: requiereAtencion(form.fecha_entrega, p.confianza?.fecha_entrega, p.fecha_entrega?.slice(0, 10) ?? ''),
    }
    const pendientes = Object.values(atencion).filter(Boolean).length

    return (
        <>
            {back}
            <PageHeader title="Revisa la actividad" subtitle="Corrige lo que haga falta. Nada se publica hasta que confirmes." />
            <Card className="max-w-3xl space-y-5">
                <p className="text-sm font-semibold text-ink-500">
                    Paralelo: <span className="text-ink-900">{paralelos.find(([id]) => id === prev.paralelo)?.[1] ?? ''}</span>
                </p>
                {p.advertencias?.length > 0 && (
                    <Alert tone="warn">
                        <ul className="list-disc space-y-0.5 pl-4">
                            {p.advertencias.map((a) => (
                                <li key={a}>{a}</li>
                            ))}
                        </ul>
                    </Alert>
                )}
                {err.message && !Object.keys(f).length && <Alert>{err.message}</Alert>}
                {pendientes > 0 ? (
                    <Alert tone="warn">
                        {pendientes === 1
                            ? 'Hay 1 campo resaltado en amarillo. Complétalo o revísalo para publicar.'
                            : `Hay ${pendientes} campos resaltados en amarillo. Complétalos o revísalos para publicar.`}
                    </Alert>
                ) : null}

                <SelectField
                    label="Asignatura"
                    value={form.asignatura}
                    onChange={set('asignatura')}
                    error={f.asignatura}
                    attention={atencion.asignatura}
                    hint={aviso(p.confianza?.asignatura, vacio('asignatura') || !form.asignatura)}
                >
                    <option value="">Selecciona una asignatura</option>
                    {prev.asignaturas_disponibles.map((a) => (
                        <option key={a.id} value={a.id}>{a.nombre}</option>
                    ))}
                </SelectField>
                <TextAreaField
                    label="Descripción"
                    rows={4}
                    maxLength={2000}
                    value={form.descripcion}
                    onChange={set('descripcion')}
                    error={f.descripcion}
                    attention={atencion.descripcion}
                    hint={aviso(p.confianza?.descripcion, vacio('descripcion'))}
                />
                <Field
                    label="Fecha de entrega"
                    type="date"
                    min={hoyISO()}
                    value={form.fecha_entrega}
                    onChange={set('fecha_entrega')}
                    error={f.fecha_entrega}
                    attention={atencion.fecha_entrega}
                    hint={aviso(p.confianza?.fecha_entrega, vacio('fecha_entrega') || !form.fecha_entrega)}
                />
                <Field
                    label="Hora de entrega"
                    type="time"
                    value={form.hora_entrega}
                    onChange={set('hora_entrega')}
                    error={f.hora_entrega}
                    hint="Opcional. Si no indicas una hora, la entrega vale todo el día."
                />
                <Field label="Tema" maxLength={150} value={form.tema} onChange={set('tema')} error={f.tema} hint={form.tema ? aviso(p.confianza?.tema) : 'Opcional.'} />
                <MaterialesInput value={form.materiales} onChange={(v) => setForm((x) => ({ ...x, materiales: v }))} error={f.materiales} />
                <ModalidadEntrega value={form.modalidad_entrega} onChange={(v) => setForm((x) => ({ ...x, modalidad_entrega: v }))} />
                {f.modalidad_entrega ? <p className="text-sm font-medium text-danger-600">{f.modalidad_entrega}</p> : null}
                <SelectorPdf archivos={pdfs} onChange={setPdfs} />
                <CheckboxField
                    label="Es una evaluación de refuerzo"
                    hint="Su nota cerrará los planes de refuerzo completados de los estudiantes en el tema que califiques."
                    checked={form.es_evaluacion_refuerzo}
                    onChange={(e) => setForm((x) => ({ ...x, es_evaluacion_refuerzo: e.target.checked }))}
                />

                <div className="flex flex-wrap justify-between gap-3 border-t border-line pt-4">
                    <Button variant="secondary" onClick={() => setPrev(null)} disabled={publish.isPending}>
                        Volver a editar el texto
                    </Button>
                    <Button
                        variant="ok"
                        onClick={() => publish.mutate()}
                        loading={publish.isPending}
                        disabled={!form.asignatura || !form.descripcion.trim() || !form.fecha_entrega}
                    >
                        <Send className="size-4" aria-hidden="true" />
                        Publicar actividad
                    </Button>
                </div>
            </Card>
        </>
    )
}
