import { useState } from 'react'
import { TriangleAlert } from 'lucide-react'

import { Alert, Card, Chip, EmptyState, PageHeader, Pagination, SelectField, Spinner, Tabs } from '../components/ui'
import { formatNota, reincidenciaLabel } from '../lib/format'
import { useAsignaciones, useDificultades, useEstudiantes } from '../lib/queries'

const TABS = [
    { id: 'DETECTADA', label: 'Vigentes' },
    { id: 'SUPERADA', label: 'Superadas' },
    { id: 'todas', label: 'Todas' },
]

const VACIO = {
    DETECTADA: 'No hay dificultades vigentes. Aparecen cuando el promedio de un tema es menor a 7,00.',
    SUPERADA: 'Aún no hay dificultades superadas.',
    todas: 'Todavía no se han detectado dificultades.',
}

const fecha = (iso) => new Date(iso).toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: 'numeric' })

export default function Dificultades() {
    const [estado, setEstado] = useState('DETECTADA')
    const [nivel, setNivel] = useState('')
    const [reincidente, setReincidente] = useState('')
    const [estudiante, setEstudiante] = useState('')
    const [asignatura, setAsignatura] = useState('')
    const [page, setPage] = useState(1)

    const estudiantes = useEstudiantes()
    const asignaciones = useAsignaciones()
    const asignaturas = [...new Map((asignaciones.data ?? []).map((a) => [a.asignatura, a.asignatura_nombre])).entries()]

    const { data, isLoading, isError } = useDificultades({
        page,
        ...(estado !== 'todas' && { estado }),
        ...(nivel && { nivel }),
        ...(reincidente && { reincidente }),
        ...(estudiante && { estudiante }),
        ...(asignatura && { asignatura }),
    })

    const filtro = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    return (
        <>
            <PageHeader title="Dificultades" subtitle="Temas donde el promedio del estudiante es menor a 7,00. Se actualizan solas al guardar notas." />

            <Tabs tabs={TABS} value={estado} label="Estado de las dificultades" onChange={(v) => { setEstado(v); setPage(1) }} />

            <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <SelectField label="Estudiante" value={estudiante} onChange={filtro(setEstudiante)}>
                    <option value="">Todos</option>
                    {estudiantes.data?.map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name}</option>
                    ))}
                </SelectField>
                <SelectField label="Asignatura" value={asignatura} onChange={filtro(setAsignatura)}>
                    <option value="">Todas</option>
                    {asignaturas.map(([id, nombre]) => (
                        <option key={id} value={id}>{nombre}</option>
                    ))}
                </SelectField>
                <SelectField label="Nivel" value={nivel} onChange={filtro(setNivel)}>
                    <option value="">Todos</option>
                    <option value="ALTA">Alta</option>
                    <option value="MODERADA">Moderada</option>
                </SelectField>
                <SelectField label="Recurrencia" value={reincidente} onChange={filtro(setReincidente)}>
                    <option value="">Todas</option>
                    <option value="true">Solo reincidentes</option>
                    <option value="false">Primera vez</option>
                </SelectField>
            </div>

            {isLoading && <Spinner />}
            {isError && <Alert>No se pudieron cargar las dificultades. Intenta de nuevo.</Alert>}
            {data && data.results.length === 0 && (
                <EmptyState icon={TriangleAlert} title="No hay dificultades para mostrar">
                    {VACIO[estado]}
                </EmptyState>
            )}

            <div className="max-w-3xl space-y-4">
                {data?.results.map((d) => {
                    const superada = d.estado === 'SUPERADA'
                    return (
                        <Card as="article" key={d.id} className={superada ? 'opacity-80' : undefined}>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="min-w-0 flex-1 basis-56">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h2 className="text-lg font-extrabold text-navy-800">{d.estudiante_nombre}</h2>
                                        {superada ? (
                                            <Chip tone="ok">Superada</Chip>
                                        ) : (
                                            <Chip tone="danger">{d.nivel === 'ALTA' ? 'Dificultad alta' : 'Dificultad moderada'}</Chip>
                                        )}
                                        {d.reincidente ? <Chip tone="danger">{reincidenciaLabel(d.veces_detectada)}</Chip> : null}
                                        {!superada && d.refuerzo === 'EN_CURSO' && <Chip>Plan de refuerzo en curso</Chip>}
                                        {!superada && d.refuerzo === 'PENDIENTE_EVALUACION' && <Chip tone="warn">Plan completado · pendiente de evaluación</Chip>}
                                    </div>
                                    <p className="text-sm text-ink-500">{d.paralelo_nombre}</p>
                                    <p className="mt-2 font-bold text-ink-900">{d.tema_nombre}</p>
                                    <p className="text-sm text-ink-500">{d.asignatura_nombre}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-3xl font-extrabold leading-none text-navy-800">{formatNota(d.promedio)}</p>
                                    <div className="mt-1.5">
                                        <Chip tone={superada ? 'ok' : d.nivel === 'ALTA' ? 'danger' : 'warn'}>{d.promedio_nivel}</Chip>
                                    </div>
                                </div>
                            </div>
                            <p className="mt-3 border-t border-line pt-3 text-sm text-ink-500">
                                {d.num_calificaciones} {d.num_calificaciones === 1 ? 'nota' : 'notas'} · Detectada el {fecha(d.detectada_en)}
                                {superada && d.superada_en && ` · Superada el ${fecha(d.superada_en)}`}
                            </p>
                        </Card>
                    )
                })}
            </div>
            {data && <Pagination page={page} count={data.count} pageSize={20} onPage={setPage} />}
        </>
    )
}
