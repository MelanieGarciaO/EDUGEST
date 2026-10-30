import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Ban, ClipboardList, Pencil, Plus, Star } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import ActividadCard from '../../components/ActividadCard'
import ActividadEditModal from '../../components/ActividadEditModal'
import { Alert, Button, ConfirmDialog, EmptyState, PageHeader, Pagination, SelectField, Spinner, Tabs } from '../../components/ui'
import { useActividades, useParalelos } from '../../lib/queries'

const TABS = [
    { id: 'pendiente', label: 'Pendientes' },
    { id: 'finalizada', label: 'Finalizadas' },
    { id: 'cancelada', label: 'Canceladas' },
]

export default function DocenteActividades() {
    const qc = useQueryClient()
    const navigate = useNavigate()
    const [vigencia, setVigencia] = useState('pendiente')
    const [paralelo, setParalelo] = useState('')
    const [page, setPage] = useState(1)
    const [editing, setEditing] = useState(null)
    const [cancelling, setCancelling] = useState(null)

    const paralelos = useParalelos()
    const { data, isLoading, isError } = useActividades({ vigencia, page, ...(paralelo && { paralelo }) })

    const cancel = useMutation({
        mutationFn: (a) => api.post(`/activities/actividades/${a.id}/cancelar/`),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['actividades'] })
            setCancelling(null)
        },
    })

    return (
        <>
            <PageHeader title="Actividades" subtitle="Publica tareas para tus paralelos y consulta las que ya enviaste.">
                <Link to="/docente/actividades/nueva">
                    <Button>
                        <Plus className="size-4" aria-hidden="true" />
                        Nueva actividad
                    </Button>
                </Link>
            </PageHeader>

            <Tabs tabs={TABS} value={vigencia} label="Estado de las actividades" onChange={(v) => { setVigencia(v); setPage(1) }} />

            <SelectField label="Paralelo" className="mb-5 max-w-xs" value={paralelo} onChange={(e) => { setParalelo(e.target.value); setPage(1) }}>
                <option value="">Todos mis paralelos</option>
                {paralelos.data?.map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre_completo}</option>
                ))}
            </SelectField>

            {isLoading && <Spinner />}
            {isError && <Alert>No se pudieron cargar las actividades. Intenta de nuevo.</Alert>}
            {data && data.results.length === 0 && (
                <EmptyState icon={ClipboardList} title="No hay actividades en este estado">
                    {vigencia === 'pendiente' ? 'Crea una con «Nueva actividad».' : 'Aquí aparecerán cuando existan.'}
                </EmptyState>
            )}
            <div className="space-y-4">
                {data?.results.map((a) => (
                    <ActividadCard key={a.id} actividad={a} adjuntosEditables>
                        {a.vigencia === 'pendiente' && (
                            <>
                                <Button variant="secondary" className="min-h-10" onClick={() => setEditing(a)} aria-label={`Editar actividad de ${a.asignatura_nombre}`}>
                                    <Pencil className="size-4" aria-hidden="true" />
                                    Editar
                                </Button>
                                <Button variant="danger" className="min-h-10" onClick={() => { cancel.reset(); setCancelling(a) }} aria-label={`Cancelar actividad de ${a.asignatura_nombre}`}>
                                    <Ban className="size-4" aria-hidden="true" />
                                    Cancelar actividad
                                </Button>
                            </>
                        )}
                        {a.vigencia === 'finalizada' && (
                            <Button variant="ok" className="min-h-10" onClick={() => navigate(`/docente/actividades/${a.id}/calificar`)} aria-label={`Calificar actividad de ${a.asignatura_nombre}`}>
                                <Star className="size-4" aria-hidden="true" />
                                Calificar
                            </Button>
                        )}
                    </ActividadCard>
                ))}
            </div>
            {data && <Pagination page={page} count={data.count} pageSize={20} onPage={setPage} />}

            <ActividadEditModal actividad={editing} onClose={() => setEditing(null)} />
            <ConfirmDialog
                open={!!cancelling}
                title="¿Cancelar esta actividad?"
                confirmLabel="Cancelar actividad"
                loading={cancel.isPending}
                error={cancel.isError ? parseApiError(cancel.error).message : null}
                onConfirm={() => cancel.mutate(cancelling)}
                onClose={() => setCancelling(null)}
            >
                Los representantes verán la actividad de {cancelling?.asignatura_nombre} como cancelada. Esta acción no se puede deshacer.
            </ConfirmDialog>
        </>
    )
}
