import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LifeBuoy } from 'lucide-react'

import { Alert, Card, Chip, EmptyState, PageHeader, Pagination, SelectField, Spinner, Tabs } from '../../components/ui'
import { PLAN_ESTADO_LABEL, PLAN_ESTADO_TONE, PLAN_NIVEL_LABEL } from '../../lib/format'
import { useEstudiantes, usePlanes } from '../../lib/queries'

const TABS = [
    { id: 'APROBADA', label: 'En curso' },
    { id: 'COMPLETADA', label: 'Completados' },
    { id: 'CANCELADA', label: 'Cancelados' },
]

const VACIO = {
    APROBADA: 'Cuando el docente apruebe un plan de refuerzo para tu representado, lo verás aquí.',
    COMPLETADA: 'Los planes con todas sus actividades cumplidas aparecerán aquí.',
    CANCELADA: 'No hay planes cancelados.',
}

export default function RepresentantePlanes() {
    const [estado, setEstado] = useState('APROBADA')
    const [estudiante, setEstudiante] = useState('')
    const [page, setPage] = useState(1)

    const estudiantes = useEstudiantes()
    const { data, isLoading, isError } = usePlanes({ estado, page, ...(estudiante && { estudiante }) })

    return (
        <>
            <PageHeader title="Planes de refuerzo" subtitle="Actividades para reforzar en casa los temas donde tu representado necesita apoyo." />

            <Tabs tabs={TABS} value={estado} label="Estado de los planes" onChange={(v) => { setEstado(v); setPage(1) }} />

            {estudiantes.data?.length > 1 && (
                <SelectField label="Estudiante" className="mb-5 max-w-xs" value={estudiante} onChange={(e) => { setEstudiante(e.target.value); setPage(1) }}>
                    <option value="">Todos mis estudiantes</option>
                    {estudiantes.data.map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name}</option>
                    ))}
                </SelectField>
            )}

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
                                </div>
                                <p className="text-sm text-ink-500">{p.asignatura_nombre} · Docente: {p.docente_nombre}</p>
                                <p className="mt-2 text-sm text-ink-700">
                                    {PLAN_NIVEL_LABEL[p.nivel]} · {p.temas.map((t) => t.tema_nombre).join(', ')}
                                </p>
                            </div>
                            <div className="min-w-36 flex-1 basis-36 sm:max-w-44">
                                <p className="mb-1 flex justify-between text-sm font-bold text-navy-800">
                                    <span>Avance</span>
                                    <span>{p.avance.porcentaje}%</span>
                                </p>
                                <div className="h-2 overflow-hidden rounded-full bg-brand-50" role="img" aria-label={`Avance ${p.avance.porcentaje}%`}>
                                    <div className="h-full rounded-full bg-ok-600" style={{ width: `${p.avance.porcentaje}%` }} />
                                </div>
                                <p className="mt-1 text-xs text-ink-500">{p.avance.actividades_cumplidas} de {p.avance.actividades_total} actividades</p>
                            </div>
                        </div>
                        <div className="mt-3 flex justify-end border-t border-line pt-3">
                            <Link to={`/representante/planes/${p.id}`} className="font-bold text-brand-700 hover:underline" aria-label={`Ver plan de ${p.estudiante_nombre} en ${p.asignatura_nombre}`}>
                                Ver actividades
                            </Link>
                        </div>
                    </Card>
                ))}
            </div>
            {data && <Pagination page={page} count={data.count} pageSize={20} onPage={setPage} />}
        </>
    )
}
