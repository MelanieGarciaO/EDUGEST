import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { GraduationCap, Pencil, Plus, Power, Search } from 'lucide-react'

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
import { useDebouncedValue } from '../../lib/hooks'
import { useParalelos, useUsuariosActivos } from '../../lib/queries'

const PAGE_SIZE = 20

export default function Estudiantes() {
    const [search, setSearch] = useState('')
    const [paralelo, setParalelo] = useState('')
    const [estado, setEstado] = useState('true')
    const [page, setPage] = useState(1)
    const [form, setForm] = useState(null)
    const [toggle, setToggle] = useState(null)
    const debounced = useDebouncedValue(search)

    const paralelos = useParalelos()
    const representantes = useUsuariosActivos('REPRESENTANTE')

    const params = {
        page,
        search: debounced || undefined,
        paralelo: paralelo || undefined,
        is_active: estado || undefined,
    }
    const list = useQuery({
        queryKey: ['estudiantes', 'list', params],
        queryFn: async () => (await api.get('/academic/estudiantes/', { params })).data,
        placeholderData: (previous) => previous,
    })

    const filter = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    const fields = [
        { name: 'first_name', label: 'Nombres' },
        { name: 'last_name', label: 'Apellidos' },
        {
            name: 'paralelo',
            label: 'Paralelo',
            type: 'select',
            options: (paralelos.data ?? []).map((p) => ({ value: p.id, label: p.nombre_completo })),
        },
        {
            name: 'representante',
            label: 'Representante',
            type: 'select',
            hint: 'Los estudiantes no tienen cuenta: su información la ve este representante.',
            options: (representantes.data ?? []).map((r) => ({ value: r.id, label: `${r.full_name} · ${r.email}` })),
        },
    ]

    const missing = !paralelos.data?.length
        ? 'Primero crea al menos un paralelo en «Estructura académica».'
        : !representantes.data?.length
            ? 'Primero crea al menos un usuario con rol Representante.'
            : ''

    const students = list.data?.results ?? []

    return (
        <>
            <PageHeader title="Estudiantes" subtitle="Cada estudiante pertenece a un paralelo y está vinculado a un representante.">
                <Button onClick={() => setForm({})} disabled={Boolean(missing) || paralelos.isPending || representantes.isPending}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo estudiante
                </Button>
            </PageHeader>
            {missing && !paralelos.isPending && !representantes.isPending && (
                <Alert tone="warn" className="mb-4">
                    {missing}
                </Alert>
            )}

            <Card className="mb-4 grid gap-4 sm:grid-cols-[1fr_14rem_11rem]">
                <div>
                    <label htmlFor="buscar-est" className="mb-1.5 block text-sm font-bold text-ink-700">
                        Buscar
                    </label>
                    <div className="relative">
                        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-ink-300" aria-hidden="true" />
                        <input
                            id="buscar-est"
                            type="search"
                            value={search}
                            onChange={filter(setSearch)}
                            placeholder="Nombre o apellido"
                            className="block min-h-11 w-full rounded-xl border border-line bg-white pr-3.5 pl-11 text-[15px] hover:border-ink-300"
                        />
                    </div>
                </div>
                <SelectField label="Paralelo" value={paralelo} onChange={filter(setParalelo)}>
                    <option value="">Todos</option>
                    {(paralelos.data ?? []).map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.nombre_completo}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Estado" value={estado} onChange={filter(setEstado)}>
                    <option value="true">Activos</option>
                    <option value="false">Inactivos</option>
                    <option value="">Todos</option>
                </SelectField>
            </Card>

            {list.isPending ? (
                <Spinner className="text-brand-600" />
            ) : list.isError ? (
                <Alert>{parseApiError(list.error).message}</Alert>
            ) : students.length === 0 ? (
                <EmptyState icon={GraduationCap} title="No hay estudiantes con estos filtros">
                    Cambia la búsqueda o registra un estudiante nuevo.
                </EmptyState>
            ) : (
                <>
                    <ListBox>
                        {students.map((s) => (
                            <Row
                                key={s.id}
                                title={s.full_name}
                                detail={`${s.paralelo_nombre} · Representante: ${s.representante_nombre}`}
                                chips={!s.is_active && <Chip tone="danger">Inactivo</Chip>}
                            >
                                <IconButton label={`Editar a ${s.full_name}`} onClick={() => setForm({ item: s })}>
                                    <Pencil className="size-5" aria-hidden="true" />
                                </IconButton>
                                <IconButton
                                    label={`${s.is_active ? 'Desactivar' : 'Activar'} a ${s.full_name}`}
                                    tone={s.is_active ? 'danger' : undefined}
                                    onClick={() => setToggle(s)}
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
                    title={form.item ? 'Editar estudiante' : 'Nuevo estudiante'}
                    endpoint="/academic/estudiantes/"
                    entity={form.item}
                    fields={fields}
                    onClose={() => setForm(null)}
                />
            )}
            <ToggleActiveDialog
                item={toggle}
                endpoint="/academic/estudiantes/"
                name={toggle?.full_name}
                noun="estudiante"
                onClose={() => setToggle(null)}
            />
        </>
    )
}
