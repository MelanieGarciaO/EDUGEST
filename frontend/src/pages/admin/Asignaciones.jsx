import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ClipboardList, Pencil, Plus, Power } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { CrudForm, ToggleActiveDialog } from '../../components/CrudForm'
import { IconButton, ListBox, Row } from '../../components/ListParts'
import {
    Alert,
    Button,
    Card,
    Chip,
    EmptyState,
    PageHeader,
    Pagination,
    SelectField,
    Spinner,
} from '../../components/ui'
import { useAsignaturasActivas, useParalelos, useUsuariosActivos } from '../../lib/queries'

const PAGE_SIZE = 20

export default function Asignaciones() {
    const [paralelo, setParalelo] = useState('')
    const [docente, setDocente] = useState('')
    const [estado, setEstado] = useState('true')
    const [page, setPage] = useState(1)
    const [form, setForm] = useState(null)
    const [toggle, setToggle] = useState(null)

    const paralelos = useParalelos()
    const asignaturas = useAsignaturasActivas()
    const docentes = useUsuariosActivos('DOCENTE')

    const params = {
        page,
        paralelo: paralelo || undefined,
        docente: docente || undefined,
        is_active: estado || undefined,
    }
    const list = useQuery({
        queryKey: ['asignaciones', 'list', params],
        queryFn: async () => (await api.get('/academic/asignaciones/', { params })).data,
        placeholderData: (previous) => previous,
    })

    const filter = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    const fields = [
        {
            name: 'docente',
            label: 'Docente',
            type: 'select',
            options: (docentes.data ?? []).map((d) => ({ value: d.id, label: `${d.full_name} · ${d.email}` })),
        },
        {
            name: 'paralelo',
            label: 'Paralelo',
            type: 'select',
            options: (paralelos.data ?? []).map((p) => ({ value: p.id, label: p.nombre_completo })),
        },
        {
            name: 'asignatura',
            label: 'Asignatura',
            type: 'select',
            hint: 'Cada asignatura tiene un solo docente por paralelo.',
            options: (asignaturas.data ?? []).map((a) => ({ value: a.id, label: a.nombre })),
        },
    ]

    const loadingCatalogs = paralelos.isPending || asignaturas.isPending || docentes.isPending
    const missing = !docentes.data?.length
        ? 'Primero crea al menos un usuario con rol Docente.'
        : !paralelos.data?.length
            ? 'Primero crea al menos un paralelo en «Estructura académica».'
            : !asignaturas.data?.length
                ? 'Primero crea al menos una asignatura en «Estructura académica».'
                : ''

    const items = list.data?.results ?? []

    return (
        <>
            <PageHeader
                title="Asignaciones docentes"
                subtitle="Define qué docente dicta cada asignatura en cada paralelo. Con esto el docente ve sus grupos."
            >
                <Button onClick={() => setForm({})} disabled={Boolean(missing) || loadingCatalogs}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nueva asignación
                </Button>
            </PageHeader>
            {missing && !loadingCatalogs && (
                <Alert tone="warn" className="mb-4">
                    {missing}
                </Alert>
            )}

            <Card className="mb-4 grid gap-4 sm:grid-cols-3">
                <SelectField label="Paralelo" value={paralelo} onChange={filter(setParalelo)}>
                    <option value="">Todos</option>
                    {(paralelos.data ?? []).map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.nombre_completo}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Docente" value={docente} onChange={filter(setDocente)}>
                    <option value="">Todos</option>
                    {(docentes.data ?? []).map((d) => (
                        <option key={d.id} value={d.id}>
                            {d.full_name}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Estado" value={estado} onChange={filter(setEstado)}>
                    <option value="true">Activas</option>
                    <option value="false">Inactivas</option>
                    <option value="">Todas</option>
                </SelectField>
            </Card>

            {list.isPending ? (
                <Spinner className="text-brand-600" />
            ) : list.isError ? (
                <Alert>{parseApiError(list.error).message}</Alert>
            ) : items.length === 0 ? (
                <EmptyState icon={ClipboardList} title="No hay asignaciones con estos filtros">
                    Crea una asignación para que el docente vea el grupo en su inicio.
                </EmptyState>
            ) : (
                <>
                    <ListBox>
                        {items.map((a) => (
                            <Row
                                key={a.id}
                                title={`${a.asignatura_nombre} · ${a.paralelo_nombre}`}
                                detail={`Docente: ${a.docente_nombre}`}
                                chips={!a.is_active && <Chip tone="danger">Inactiva</Chip>}
                            >
                                <IconButton label={`Editar ${a.asignatura_nombre} de ${a.paralelo_nombre}`} onClick={() => setForm({ item: a })}>
                                    <Pencil className="size-5" aria-hidden="true" />
                                </IconButton>
                                <IconButton
                                    label={`${a.is_active ? 'Desactivar' : 'Activar'} ${a.asignatura_nombre} de ${a.paralelo_nombre}`}
                                    tone={a.is_active ? 'danger' : undefined}
                                    onClick={() => setToggle(a)}
                                >
                                    <Power className="size-5" aria-hidden="true" />
                                </IconButton>
                            </Row>
                        ))}
                    </ListBox>
                    <Pagination page={page} count={list.data.count} pageSize={PAGE_SIZE} onPage={setPage} />
                </>
            )}

            {form && (
                <CrudForm
                    title={form.item ? 'Editar asignación' : 'Nueva asignación'}
                    endpoint="/academic/asignaciones/"
                    entity={form.item}
                    fields={fields}
                    onClose={() => setForm(null)}
                />
            )}
            <ToggleActiveDialog
                item={toggle}
                endpoint="/academic/asignaciones/"
                name={toggle ? `${toggle.asignatura_nombre} · ${toggle.paralelo_nombre}` : ''}
                noun="asignación"
                onClose={() => setToggle(null)}
            />
        </>
    )
}
