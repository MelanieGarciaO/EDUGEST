import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Ban, CheckCircle2, Pencil, Plus, RotateCcw, Send, Trash2 } from 'lucide-react'

import { api, fetchAll, parseApiError } from '../../api/client'
import { PlanHeader, PlanTemas } from '../../components/PlanView'
import { Alert, Button, ConfirmDialog, Field, Modal, PageHeader, SelectField, Spinner, TextAreaField } from '../../components/ui'
import { ESTRATEGIAS, NIVEL_LABEL } from '../../lib/format'
import { usePlan } from '../../lib/queries'

/** Ejecuta un POST/PATCH/DELETE sobre el plan y refresca sus datos. */
function useAccion(planId, fn) {
    const qc = useQueryClient()
    return useMutation({
        mutationFn: fn,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plan', planId] })
            qc.invalidateQueries({ queryKey: ['planes'] })
        },
    })
}

const mensaje = (m) => (m.isError ? parseApiError(m.error) : null)

function ObjetivoModal({ tema, planId, onClose }) {
    const [texto, setTexto] = useState('')
    const guardar = useAccion(planId, async () => (await api.patch(`/reinforcement/temas-plan/${tema.id}/`, { objetivo: texto })).data)
    useEffect(() => {
        if (tema) {
            setTexto(tema.objetivo)
            guardar.reset()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tema])
    const err = mensaje(guardar)
    return (
        <Modal
            open={!!tema}
            onClose={onClose}
            title={tema ? `Objetivo de «${tema.tema_nombre}»` : ''}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={guardar.isPending}>Cancelar</Button>
                    <Button loading={guardar.isPending} disabled={!texto.trim()} onClick={() => guardar.mutate(undefined, { onSuccess: onClose })}>
                        Guardar cambios
                    </Button>
                </>
            }
        >
            {err && <Alert className="mb-3">{err.fields.objetivo ?? err.message}</Alert>}
            <TextAreaField label="Objetivo" rows={4} value={texto} onChange={(e) => setTexto(e.target.value)} />
        </Modal>
    )
}

/** Edita una actividad existente (actividad) o agrega una propia (tema). */
function ActividadModal({ actividad, tema, planId, onClose }) {
    const abierto = !!(actividad || tema)
    const [f, setF] = useState({ titulo: '', instrucciones: '', duracion: '', estrategia: '' })
    const guardar = useAccion(planId, async () => {
        const body = { titulo: f.titulo.trim(), instrucciones: f.instrucciones.trim(), duracion_minutos: f.duracion ? Number(f.duracion) : null, estrategia: f.estrategia }
        return actividad
            ? (await api.patch(`/reinforcement/actividades/${actividad.id}/`, body)).data
            : (await api.post(`/reinforcement/temas-plan/${tema.id}/actividades/`, body)).data
    })
    useEffect(() => {
        if (abierto) {
            setF({ titulo: actividad?.titulo ?? '', instrucciones: actividad?.instrucciones ?? '', duracion: actividad?.duracion_minutos ? String(actividad.duracion_minutos) : '', estrategia: actividad?.estrategia ?? '' })
            guardar.reset()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [actividad, tema])
    const err = mensaje(guardar)
    const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
    return (
        <Modal
            open={abierto}
            onClose={onClose}
            title={actividad ? 'Editar actividad' : 'Agregar actividad propia'}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={guardar.isPending}>Cancelar</Button>
                    <Button loading={guardar.isPending} disabled={!f.titulo.trim() || !f.instrucciones.trim()} onClick={() => guardar.mutate(undefined, { onSuccess: onClose })}>
                        {actividad ? 'Guardar cambios' : 'Agregar actividad'}
                    </Button>
                </>
            }
        >
            <div className="space-y-4">
                {err && !Object.keys(err.fields).length && <Alert>{err.message}</Alert>}
                <Field label="Título" maxLength={200} value={f.titulo} onChange={set('titulo')} error={err?.fields.titulo} />
                <TextAreaField label="Instrucciones" rows={5} maxLength={2000} value={f.instrucciones} onChange={set('instrucciones')} error={err?.fields.instrucciones} />
                <div className="grid gap-4 sm:grid-cols-2">
                    <SelectField label="Estrategia" value={f.estrategia} onChange={set('estrategia')} error={err?.fields.estrategia}>
                        <option value="">Sin especificar</option>
                        {ESTRATEGIAS.map((e) => (
                            <option key={e.value} value={e.value}>{e.label}</option>
                        ))}
                    </SelectField>
                    <Field label="Duración (min)" type="number" min="1" max="240" value={f.duracion} onChange={set('duracion')} error={err?.fields.duracion_minutos} hint="Opcional." />
                </div>
            </div>
        </Modal>
    )
}

/** Agrega una actividad desde el banco de recursos. */
function BancoModal({ tema, plan, onClose }) {
    const [recurso, setRecurso] = useState('')
    const recursos = useQuery({
        queryKey: ['recursos-plan', plan.asignatura],
        enabled: !!tema,
        queryFn: () => fetchAll('/reinforcement/recursos/', { asignatura: plan.asignatura, is_active: 'true' }),
    })
    const guardar = useAccion(plan.id, async () => (await api.post(`/reinforcement/temas-plan/${tema.id}/actividades/`, { recurso: Number(recurso) })).data)
    useEffect(() => {
        if (tema) {
            setRecurso('')
            guardar.reset()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tema])

    const usados = new Set((tema?.actividades ?? []).map((a) => a.recurso))
    const disponibles = (recursos.data ?? []).filter((r) => !usados.has(r.id))
    const delTema = disponibles.filter((r) => r.tema === tema?.tema)
    const otros = disponibles.filter((r) => r.tema !== tema?.tema)
    const opcion = (r) => (
        <option key={r.id} value={r.id}>{r.titulo} · {NIVEL_LABEL[r.nivel]}{r.tema !== tema?.tema ? ` · ${r.tema_nombre}` : ''}</option>
    )
    const err = mensaje(guardar)

    return (
        <Modal
            open={!!tema}
            onClose={onClose}
            title="Agregar desde el banco de recursos"
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={guardar.isPending}>Cancelar</Button>
                    <Button loading={guardar.isPending} disabled={!recurso} onClick={() => guardar.mutate(undefined, { onSuccess: onClose })}>
                        Agregar actividad
                    </Button>
                </>
            }
        >
            <div className="space-y-4">
                {err && <Alert>{err.fields.recurso ?? err.message}</Alert>}
                {recursos.isLoading && <Spinner />}
                {recursos.isSuccess && disponibles.length === 0 && (
                    <Alert tone="warn">No hay más recursos disponibles para esta asignatura. Puedes agregar una actividad propia o cargar recursos en el banco.</Alert>
                )}
                {disponibles.length > 0 && (
                    <SelectField label="Recurso" value={recurso} onChange={(e) => setRecurso(e.target.value)}>
                        <option value="">Selecciona un recurso</option>
                        {delTema.length > 0 && <optgroup label={`De «${tema?.tema_nombre}»`}>{delTema.map(opcion)}</optgroup>}
                        {otros.length > 0 && <optgroup label="Otros temas de la asignatura">{otros.map(opcion)}</optgroup>}
                    </SelectField>
                )}
            </div>
        </Modal>
    )
}

export default function PlanDetalle() {
    const { id } = useParams()
    const { data: plan, isLoading, isError } = usePlan(id)

    const [objetivoDe, setObjetivoDe] = useState(null)
    const [editando, setEditando] = useState(null)
    const [propiaEn, setPropiaEn] = useState(null)
    const [bancoEn, setBancoEn] = useState(null)
    const [quitando, setQuitando] = useState(null)
    const [confirm, setConfirm] = useState(null) // 'aprobar' | 'cancelar'

    const planAccion = useAccion(id, async () => (await api.post(`/reinforcement/planes/${id}/${confirm}/`)).data)
    const quitar = useAccion(id, async () => api.delete(`/reinforcement/actividades/${quitando.id}/`))
    const seguimiento = useAccion(id, async ({ actividad, accion }) => (await api.post(`/reinforcement/actividades/${actividad.id}/${accion}/`)).data)

    const propuesta = plan?.estado === 'PROPUESTA'
    const vigente = propuesta || plan?.estado === 'APROBADA'
    const errSeg = mensaje(seguimiento)

    const accionesActividad = (a) => {
        if (propuesta) {
            return (
                <>
                    <Button variant="secondary" className="min-h-9 px-3 text-sm" onClick={() => setEditando(a)} aria-label={`Editar ${a.titulo}`}>
                        <Pencil className="size-4" aria-hidden="true" />
                        Editar
                    </Button>
                    <Button variant="danger" className="min-h-9 px-3 text-sm" onClick={() => { quitar.reset(); setQuitando(a) }} aria-label={`Quitar ${a.titulo}`}>
                        <Trash2 className="size-4" aria-hidden="true" />
                        Quitar
                    </Button>
                </>
            )
        }
        if (plan.estado !== 'APROBADA' && plan.estado !== 'COMPLETADA') return null
        return a.estado === 'CUMPLIDA' ? (
            <Button variant="secondary" className="min-h-9 px-3 text-sm" loading={seguimiento.isPending} onClick={() => seguimiento.mutate({ actividad: a, accion: 'reabrir' })} aria-label={`Reabrir ${a.titulo}`}>
                <RotateCcw className="size-4" aria-hidden="true" />
                Reabrir
            </Button>
        ) : (
            <Button variant="ok" className="min-h-9 px-3 text-sm" loading={seguimiento.isPending} onClick={() => seguimiento.mutate({ actividad: a, accion: 'cumplir' })} aria-label={`Marcar cumplida ${a.titulo}`}>
                <CheckCircle2 className="size-4" aria-hidden="true" />
                Marcar cumplida
            </Button>
        )
    }

    const accionesTema = (t) =>
        propuesta ? (
            <>
                <Button variant="secondary" className="min-h-9 px-3 text-sm" onClick={() => setObjetivoDe(t)} aria-label={`Editar objetivo de ${t.tema_nombre}`}>
                    <Pencil className="size-4" aria-hidden="true" />
                    Editar objetivo
                </Button>
                <Button variant="secondary" className="min-h-9 px-3 text-sm" onClick={() => setBancoEn(t)} aria-label={`Agregar del banco a ${t.tema_nombre}`}>
                    <Plus className="size-4" aria-hidden="true" />
                    Del banco
                </Button>
                <Button variant="secondary" className="min-h-9 px-3 text-sm" onClick={() => setPropiaEn(t)} aria-label={`Agregar actividad propia a ${t.tema_nombre}`}>
                    <Plus className="size-4" aria-hidden="true" />
                    Actividad propia
                </Button>
            </>
        ) : null

    return (
        <>
            <Link to="/docente/planes" className="mb-4 inline-flex items-center gap-1.5 text-sm font-bold text-brand-700 hover:underline">
                <ArrowLeft className="size-4" aria-hidden="true" />
                Volver a planes
            </Link>
            <PageHeader title="Plan de refuerzo">
                {vigente && (
                    <div className="flex flex-wrap gap-2">
                        <Button variant="danger" onClick={() => { planAccion.reset(); setConfirm('cancelar') }}>
                            <Ban className="size-4" aria-hidden="true" />
                            Cancelar plan
                        </Button>
                        {propuesta && (
                            <Button variant="ok" onClick={() => { planAccion.reset(); setConfirm('aprobar') }}>
                                <Send className="size-4" aria-hidden="true" />
                                Aprobar y compartir
                            </Button>
                        )}
                    </div>
                )}
            </PageHeader>

            {isLoading && <Spinner />}
            {isError && <Alert>No se encontró el plan o no tienes acceso a él.</Alert>}
            {plan && (
                <div className="max-w-3xl space-y-5">
                    {propuesta && (
                        <Alert tone="warn">Este plan es una propuesta: la familia aún no lo ve. Revísalo, ajústalo y apruébalo para compartirlo.</Alert>
                    )}
                    {errSeg && <Alert>{errSeg.message}</Alert>}
                    <PlanHeader plan={plan} docente />
                    <PlanTemas plan={plan} actions={accionesActividad} temaActions={accionesTema} evidencias="ver" />
                </div>
            )}

            <ObjetivoModal tema={objetivoDe} planId={id} onClose={() => setObjetivoDe(null)} />
            <ActividadModal actividad={editando} tema={propiaEn} planId={id} onClose={() => { setEditando(null); setPropiaEn(null) }} />
            {plan && <BancoModal tema={bancoEn} plan={plan} onClose={() => setBancoEn(null)} />}

            <ConfirmDialog
                open={!!quitando}
                title="¿Quitar esta actividad?"
                confirmLabel="Quitar actividad"
                loading={quitar.isPending}
                error={mensaje(quitar)?.message}
                onConfirm={() => quitar.mutate(undefined, { onSuccess: () => setQuitando(null) })}
                onClose={() => setQuitando(null)}
            >
                «{quitando?.titulo}» se eliminará de este plan. El recurso sigue disponible en el banco.
            </ConfirmDialog>

            <ConfirmDialog
                open={!!confirm}
                title={confirm === 'aprobar' ? '¿Aprobar y compartir el plan?' : '¿Cancelar el plan?'}
                confirmLabel={confirm === 'aprobar' ? 'Aprobar y compartir' : 'Cancelar plan'}
                tone={confirm === 'aprobar' ? 'ok' : 'danger'}
                loading={planAccion.isPending}
                error={mensaje(planAccion)?.message}
                onConfirm={() => planAccion.mutate(undefined, { onSuccess: () => setConfirm(null) })}
                onClose={() => setConfirm(null)}
            >
                {confirm === 'aprobar'
                    ? 'El representante verá el plan y podrá marcar las actividades como cumplidas. Ya no podrás editar sus temas ni actividades.'
                    : 'El plan dejará de estar vigente y podrás generar uno nuevo para este estudiante y asignatura. Esta acción no se puede deshacer.'}
            </ConfirmDialog>
        </>
    )
}
