import { useState } from 'react'
import { ClipboardList } from 'lucide-react'

import ActividadCard from '../../components/ActividadCard'
import { Alert, EmptyState, PageHeader, Pagination, SelectField, Spinner, Tabs } from '../../components/ui'
import { useActividades, useEstudiantes } from '../../lib/queries'

const TABS = [
    { id: 'todas', label: 'Todas' },
    { id: 'pendiente', label: 'Pendientes' },
    { id: 'finalizada', label: 'Finalizadas' },
]

const VACIO = {
    todas: 'Cuando los docentes publiquen tareas, las verás aquí.',
    pendiente: 'No hay tareas por entregar. ¡Todo al día!',
    finalizada: 'Aún no hay tareas con la fecha vencida.',
}

export default function RepresentanteActividades() {
    const [tab, setTab] = useState('todas')
    const [estudiante, setEstudiante] = useState('')
    const [page, setPage] = useState(1)

    const estudiantes = useEstudiantes()
    const { data, isLoading, isError } = useActividades({
        page,
        ...(tab !== 'todas' && { vigencia: tab }),
        ...(estudiante && { estudiante }),
    })

    const nombre = estudiantes.data?.find((e) => String(e.id) === estudiante)
    const subtitulo = nombre
        ? `Tareas de ${nombre.full_name}.`
        : 'Tareas de tus estudiantes, de la más próxima a la más lejana.'

    return (
        <>
            <PageHeader title="Actividades" subtitle={subtitulo} />

            <Tabs tabs={TABS} value={tab} label="Filtrar actividades" onChange={(v) => { setTab(v); setPage(1) }} />

            {estudiantes.data?.length > 1 && (
                <SelectField label="Estudiante" className="mb-5 max-w-xs" value={estudiante} onChange={(e) => { setEstudiante(e.target.value); setPage(1) }}>
                    <option value="">Todos mis estudiantes</option>
                    {estudiantes.data.map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name}</option>
                    ))}
                </SelectField>
            )}

            {isLoading && <Spinner />}
            {isError && <Alert>No se pudieron cargar las actividades. Intenta de nuevo.</Alert>}
            {data && data.results.length === 0 && (
                <EmptyState icon={ClipboardList} title="No hay actividades para mostrar">
                    {VACIO[tab]}
                </EmptyState>
            )}
            <div className="space-y-4">
                {data?.results.map((a) => (
                    <ActividadCard key={a.id} actividad={a} showDocente />
                ))}
            </div>
            {data && <Pagination page={page} count={data.count} pageSize={20} onPage={setPage} />}
        </>
    )
}
