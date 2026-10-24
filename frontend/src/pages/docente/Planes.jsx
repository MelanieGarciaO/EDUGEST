import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LifeBuoy, Plus, Trash2 } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { Alert, Button, Card, Chip, EmptyState, Field, Modal, PageHeader, Pagination, SelectField, Spinner, Tabs } from '../../components/ui'
import { PLAN_ESTADO_LABEL, PLAN_ESTADO_TONE, PLAN_NIVEL_LABEL, evaluacionPlan, formatNota } from '../../lib/format'
import { useAsignaciones, useEstudiantes, useParalelos, usePlanes, useTemasActivos } from '../../lib/queries'

const TABS = [
    { id: 'PROPUESTA', label: 'Propuestas' },
    { id: 'APROBADA', label: 'Aprobados' },
    { id: 'COMPLETADA', label: 'Completados' },
    { id: 'CANCELADA', label: 'Cancelados' },
]

const MAX_TEMAS = 3

const VACIO = {
    PROPUESTA: 'Genera un plan para un estudiante con dificultades y revísalo antes de enviarlo a la familia.',
    APROBADA: 'Los planes aprobados y en curso aparecerán aquí.',
    COMPLETADA: 'Los planes con todas sus actividades cumplidas aparecerán aquí.',
    CANCELADA: 'No hay planes cancelados.',
}

function GenerarPlanModal({ open, onClose }) {
    const navigate = useNavigate()
    const qc = useQueryClient()
    const estudiantes = useEstudiantes()
    const asignaciones = useAsignaciones()
    const paralelos = useParalelos()
    const temas = useTemasActivos()
    const [estudiante, setEstudiante] = useState('')
    const [asignatura, setAsignatura] = useState('')
    const [manuales, setManuales] = useState([]) // [{ tema: '', motivo: '' }]

    const alumno = estudiantes.data?.find((e) => String(e.id) === estudiante)
    const materias = (asignaciones.data ?? []).filter((a) => a.paralelo === alumno?.paralelo)
    const gradoId = paralelos.data?.find((p) => p.id === alumno?.paralelo)?.grado
    const temasDelAlumno = (temas.data ?? []).filter((t) => t.grado === gradoId && String(t.asignatura) === asignatura)
    const etiqueta = (t) => (t.padre_nombre ? `${t.padre_nombre} › ${t.nombre}` : t.nombre)

    // Dificultades vigentes: entran solas al plan, por eso no se ofrecen como refuerzo manual.
    const vigentes = useQuery({
        queryKey: ['dificultades', { estudiante, asignatura, estado: 'DETECTADA' }],
        queryFn: async () => (await api.get('/grades/dificultades/', { params: { estudiante, asignatura, estado: 'DETECTADA' } })).data,
        enabled: !!estudiante && !!asignatura,
    })
    const dificultades = vigentes.data?.results ?? vigentes.data ?? []
    const conDificultad = new Set(dificultades.map((d) => d.tema))
    const temasManuales = temasDelAlumno.filter((t) => !conDificultad.has(t.id))

    const incompletos = manuales.some((m) => !m.tema || !m.motivo.trim())

    const generar = useMutation({
        mutationFn: async () => {
            const body = { estudiante: Number(estudiante), asignatura: Number(asignatura) }
            if (manuales.length) body.temas_manuales = manuales.map((m) => ({ tema: Number(m.tema), motivo: m.motivo.trim() }))
            return (await api.post('/reinforcement/planes/generar/', body)).data
        },
        onSuccess: (plan) => {
            qc.invalidateQueries({ queryKey: ['planes'] })
            close()
            navigate(`/docente/planes/${plan.id}`)
        },
    })

    function close() {
        setEstudiante('')
        setAsignatura('')
        setManuales([])
        generar.reset()
        onClose()
    }

    const cambiar = (i, campo) => (e) => setManuales((ms) => ms.map((m, j) => (j === i ? { ...m, [campo]: e.target.value } : m)))
    const error = generar.isError ? parseApiError(generar.error) : null

    return (
        <Modal
            open={open}
            onClose={close}
            title="Generar plan de refuerzo"
            size="lg"
            footer={
                <>
                    <Button variant="secondary" onClick={close} disabled={generar.isPending}>
                        Cancelar
                    </Button>
                    <Button onClick={() => generar.mutate()} loading={generar.isPending} disabled={!estudiante || !asignatura || incompletos}>
                        Generar plan
                    </Button>
                </>
            }
        >
            <div className="space-y-4">
                <p className="text-sm text-ink-500">
                    El plan se arma con las dificultades vigentes del estudiante en la asignatura (hasta {MAX_TEMAS} temas) y actividades del banco de recursos. Podrás revisarlo antes de publicarlo.
                </p>
                {error && <Alert>{error.fields.temas_manuales ?? error.fields.asignatura ?? error.fields.estudiante ?? error.message}</Alert>}
                <SelectField
                    label="Estudiante"
                    value={estudiante}
                    onChange={(e) => {
                        setEstudiante(e.target.value)
                        setAsignatura('')
                        setManuales([])
                    }}
                >
                    <option value="">Selecciona un estudiante</option>
                    {estudiantes.data?.map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name} · {e.paralelo_nombre}</option>
                    ))}
                </SelectField>
                <SelectField
                    label="Asignatura"
                    value={asignatura}
                    onChange={(e) => {
                        setAsignatura(e.target.value)
                        setManuales([])
                    }}
                    disabled={!estudiante}
                >
                    <option value="">Selecciona una asignatura</option>
                    {materias.map((a) => (
                        <option key={a.id} value={a.asignatura}>{a.asignatura_nombre}</option>
                    ))}
                </SelectField>

                {asignatura && vigentes.isSuccess && (
                    <div className="rounded-xl border border-line p-4">
                        <p className="text-sm font-bold text-ink-700">Dificultades que se incluirán automáticamente</p>
                        {dificultades.length === 0 ? (
                            <p className="mt-1 text-sm text-ink-500">Este estudiante no tiene dificultades en la asignatura. Para generar un plan, agrega un tema a reforzar.</p>
                        ) : (
                            <ul className="mt-2 flex flex-wrap gap-2">
                                {dificultades.map((d) => (
                                    <li key={d.id}>
                                        <Chip tone={d.nivel === 'ALTA' ? 'danger' : 'warn'}>
                                            {`${d.tema_nombre} · ${formatNota(d.promedio)}${d.reincidente ? ' · reincidente' : ''}`}
                                        </Chip>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                )}

                {asignatura && (
                    <fieldset className="space-y-3 rounded-xl border border-line p-4">
                        <legend className="px-1 text-sm font-bold text-ink-700">Reforzar un tema que no tiene dificultad (opcional)</legend>
                        <p className="text-sm text-ink-500">
                            Úsalo cuando el estudiante llega a 7 pero falla en una destreza concreta. Cuenta dentro del máximo de {MAX_TEMAS} temas del plan y tiene prioridad sobre las dificultades.
                        </p>
                        {manuales.map((m, i) => (
                            <div key={i} className="space-y-3 rounded-xl bg-brand-50 p-3">
                                <SelectField label={`Tema ${i + 1}`} value={m.tema} onChange={cambiar(i, 'tema')}>
                                    <option value="">Selecciona un tema o subtema</option>
                                    {temasManuales
                                        .filter((t) => String(t.id) === m.tema || !manuales.some((x) => x.tema === String(t.id)))
                                        .map((t) => (
                                            <option key={t.id} value={t.id}>{etiqueta(t)}</option>
                                        ))}
                                </SelectField>
                                <Field label="Motivo" maxLength={300} value={m.motivo} onChange={cambiar(i, 'motivo')} hint="Por ejemplo: «Falla al comparar fracciones con distinto denominador»." />
                                <Button variant="ghost" onClick={() => setManuales((ms) => ms.filter((_, j) => j !== i))}>
                                    <Trash2 className="size-4" aria-hidden="true" />
                                    Quitar este tema
                                </Button>
                            </div>
                        ))}
                        {temas.isSuccess && temasDelAlumno.length === 0 && (
                            <p className="text-sm font-semibold text-warn-600">No hay temas creados para este grado y asignatura.</p>
                        )}
                        {temasDelAlumno.length > 0 && temasManuales.length === 0 && (
                            <p className="text-sm text-ink-500">Todos los temas de la asignatura ya tienen dificultad detectada y entran solos al plan.</p>
                        )}
                        {manuales.length < MAX_TEMAS && temasManuales.length > 0 && (
                            <Button variant="secondary" onClick={() => setManuales((ms) => [...ms, { tema: '', motivo: '' }])}>
                                <Plus className="size-4" aria-hidden="true" />
                                Agregar un tema a reforzar
                            </Button>
                        )}
                    </fieldset>
                )}
            </div>
        </Modal>
    )
}

export default function DocentePlanes() {
    const [estado, setEstado] = useState('PROPUESTA')
    const [page, setPage] = useState(1)
    const [generando, setGenerando] = useState(false)
    const { data, isLoading, isError } = usePlanes({ estado, page })

    return (
        <>
            <PageHeader title="Planes de refuerzo" subtitle="Propuestas de refuerzo para estudiantes con dificultades en tus asignaturas.">
                <Button onClick={() => setGenerando(true)}>
                    <Plus className="size-4" aria-hidden="true" />
                    Generar plan
                </Button>
            </PageHeader>

            <Tabs tabs={TABS} value={estado} label="Estado de los planes" onChange={(v) => { setEstado(v); setPage(1) }} />

            {isLoading && <Spinner />}
            {isError && <Alert>No se pudieron cargar los planes. Intenta de nuevo.</Alert>}
            {data && data.results.length === 0 && (
                <EmptyState icon={LifeBuoy} title="No hay planes en este estado">
                    {VACIO[estado]}
                </EmptyState>
            )}

            <div className="max-w-3xl space-y-4">
                {data?.results.map((p) => (
                    <Card as="article" key={p.id}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0 flex-1 basis-56">
                                <div className="flex flex-wrap items-center gap-2">
                                    <h2 className="text-lg font-extrabold text-navy-800">{p.estudiante_nombre}</h2>
                                    <Chip tone={PLAN_ESTADO_TONE[p.estado]}>{PLAN_ESTADO_LABEL[p.estado]}</Chip>
                                    {evaluacionPlan(p.evaluacion) && <Chip tone={evaluacionPlan(p.evaluacion).tone}>{evaluacionPlan(p.evaluacion).label}</Chip>}
                                    {p.revisado_en ? <Chip tone="ok">Revisado por la familia</Chip> : null}
                                </div>
                                <p className="text-sm text-ink-500">{p.asignatura_nombre} · {p.paralelo_nombre}</p>
                                <p className="mt-2 text-sm text-ink-700">
                                    {PLAN_NIVEL_LABEL[p.nivel]} · {p.temas.length} {p.temas.length === 1 ? 'tema' : 'temas'}:{' '}
                                    {p.temas.map((t) => t.tema_nombre).join(', ')}
                                </p>
                            </div>
                            <div className="text-right">
                                <p className="text-2xl font-extrabold leading-none text-navy-800">{p.avance.porcentaje}%</p>
                                <p className="mt-1 text-xs text-ink-500">{p.avance.actividades_cumplidas} de {p.avance.actividades_total} actividades</p>
                            </div>
                        </div>
                        <div className="mt-3 flex justify-end border-t border-line pt-3">
                            <Link to={`/docente/planes/${p.id}`} className="font-bold text-brand-700 hover:underline" aria-label={`Ver plan de ${p.estudiante_nombre} en ${p.asignatura_nombre}`}>
                                Ver plan
                            </Link>
                        </div>
                    </Card>
                ))}
            </div>
            {data && <Pagination page={page} count={data.count} pageSize={20} onPage={setPage} />}

            <GenerarPlanModal open={generando} onClose={() => setGenerando(false)} />
        </>
    )
}
