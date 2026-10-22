import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Library, Pencil, Plus, Power, Search } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { ToggleActiveDialog } from '../components/CrudForm'
import { IconButton, ListBox } from '../components/ListParts'
import {
    Alert,
    Button,
    Card,
    Chip,
    EmptyState,
    Field,
    Modal,
    PageHeader,
    Pagination,
    SelectField,
    Spinner,
    TextAreaField,
} from '../components/ui'
import { ESTRATEGIA_LABEL, ESTRATEGIAS, NIVEL_LABEL, NIVEL_TONE, NIVELES, temaLabel } from '../lib/format'
import { useDebouncedValue } from '../lib/hooks'
import { useAsignaturasActivas, useGrados, useTemasActivos } from '../lib/queries'

const PAGE_SIZE = 20
const ENDPOINT = '/reinforcement/recursos/'

function RecursoForm({ item, temas, onClose }) {
    const queryClient = useQueryClient()
    const editing = Boolean(item)
    const [values, setValues] = useState({
        tema: item?.tema ?? '',
        nivel: item?.nivel ?? '',
        estrategia: item?.estrategia ?? 'INDIVIDUAL',
        titulo: item?.titulo ?? '',
        instrucciones: item?.instrucciones ?? '',
        duracion_minutos: item?.duracion_minutos ?? '',
    })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))

    const save = useMutation({
        mutationFn: async (payload) =>
            editing ? (await api.patch(`${ENDPOINT}${item.id}/`, payload)).data : (await api.post(ENDPOINT, payload)).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['recursos'] })
            onClose()
        },
        onError: (err) => {
            const { fields, message } = parseApiError(err)
            setErrors(fields)
            setGeneral(Object.keys(fields).length ? '' : message)
        },
    })

    function onSubmit(e) {
        e.preventDefault()
        const local = {}
        if (!values.tema) local.tema = 'Elige el tema.'
        if (!values.nivel) local.nivel = 'Elige el nivel.'
        if (!values.estrategia) local.estrategia = 'Elige la estrategia.'
        if (!values.titulo.trim()) local.titulo = 'Escribe el título.'
        if (!values.instrucciones.trim()) local.instrucciones = 'Escribe las instrucciones para el estudiante.'
        const minutos = values.duracion_minutos === '' ? null : Number(values.duracion_minutos)
        if (minutos !== null && (!Number.isInteger(minutos) || minutos < 1 || minutos > 240)) {
            local.duracion_minutos = 'Indica un número de minutos entre 1 y 240.'
        }
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return
        const payload = {
            nivel: values.nivel,
            estrategia: values.estrategia,
            titulo: values.titulo.trim(),
            instrucciones: values.instrucciones.trim(),
            duracion_minutos: minutos,
        }
        save.mutate(editing ? payload : { ...payload, tema: Number(values.tema) })
    }

    return (
        <Modal
            open
            size="lg"
            onClose={onClose}
            title={editing ? 'Editar recurso' : 'Nuevo recurso'}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
                        Cancelar
                    </Button>
                    <Button type="submit" form="recurso-form" loading={save.isPending}>
                        {editing ? 'Guardar cambios' : 'Crear recurso'}
                    </Button>
                </>
            }
        >
            <form id="recurso-form" onSubmit={onSubmit} noValidate className="space-y-4">
                {general && <Alert>{general}</Alert>}
                {editing ? (
                    <p className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-ink-700">
                        {item.grado_nombre} · {item.asignatura_nombre} · {item.tema_nombre}
                        <span className="block text-ink-500">El tema de un recurso no se puede cambiar.</span>
                    </p>
                ) : (
                    <SelectField label="Tema" value={values.tema} onChange={set('tema')} error={errors.tema}>
                        <option value="">Elige un tema o subtema</option>
                        {temas.map((t) => (
                            <option key={t.id} value={t.id}>
                                {temaLabel(t)}
                            </option>
                        ))}
                    </SelectField>
                )}
                <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
                    <SelectField label="Nivel de dificultad" value={values.nivel} onChange={set('nivel')} error={errors.nivel}>
                        <option value="">Elige un nivel</option>
                        {NIVELES.map((n) => (
                            <option key={n.value} value={n.value}>
                                {n.label}
                            </option>
                        ))}
                    </SelectField>
                    <Field
                        label="Duración (min)"
                        type="number"
                        min="1"
                        max="240"
                        value={values.duracion_minutos}
                        onChange={set('duracion_minutos')}
                        error={errors.duracion_minutos}
                        hint="Opcional"
                    />
                </div>
                <SelectField label="Estrategia de refuerzo" value={values.estrategia} onChange={set('estrategia')} error={errors.estrategia}>
                    {ESTRATEGIAS.map((e) => (
                        <option key={e.value} value={e.value}>
                            {e.label}
                        </option>
                    ))}
                </SelectField>
                <Field label="Título" value={values.titulo} onChange={set('titulo')} error={errors.titulo} maxLength={200} />
                <TextAreaField
                    label="Instrucciones"
                    value={values.instrucciones}
                    onChange={set('instrucciones')}
                    error={errors.instrucciones}
                    maxLength={2000}
                    hint="Lo que el estudiante debe hacer en casa, explicado con claridad."
                />
            </form>
        </Modal>
    )
}

export default function Recursos() {
    const { user } = useAuth()
    const isAdmin = user.role === 'ADMINISTRADOR'
    const [search, setSearch] = useState('')
    const [grado, setGrado] = useState('')
    const [asignatura, setAsignatura] = useState('')
    const [nivel, setNivel] = useState('')
    const [estado, setEstado] = useState('true')
    const [page, setPage] = useState(1)
    const [form, setForm] = useState(null)
    const [toggle, setToggle] = useState(null)
    const debounced = useDebouncedValue(search)

    const grados = useGrados()
    const asignaturas = useAsignaturasActivas()
    const temas = useTemasActivos()

    const params = {
        page,
        search: debounced || undefined,
        grado: grado || undefined,
        asignatura: asignatura || undefined,
        nivel: nivel || undefined,
        is_active: estado || undefined,
    }
    const list = useQuery({
        queryKey: ['recursos', params],
        queryFn: async () => (await api.get(ENDPOINT, { params })).data,
        placeholderData: (previous) => previous,
    })

    const filter = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    const items = list.data?.results ?? []
    const canEdit = (r) => isAdmin || r.creado_por === user.id

    return (
        <>
            <PageHeader
                title="Banco de recursos"
                subtitle="Actividades de refuerzo por tema y nivel. De aquí salen las propuestas de los planes de refuerzo."
            >
                <Button onClick={() => setForm({})} disabled={!temas.data?.length}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo recurso
                </Button>
            </PageHeader>
            {!temas.isPending && !temas.data?.length && (
                <Alert tone="warn" className="mb-4">
                    {isAdmin
                        ? 'Primero crea temas en la sección «Temas».'
                        : 'Todavía no hay temas para tus asignaturas. Pide al administrador que los cree.'}
                </Alert>
            )}

            <Card className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <div className="sm:col-span-2 lg:col-span-5">
                    <label htmlFor="buscar-rec" className="mb-1.5 block text-sm font-bold text-ink-700">
                        Buscar
                    </label>
                    <div className="relative">
                        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-ink-300" aria-hidden="true" />
                        <input
                            id="buscar-rec"
                            type="search"
                            value={search}
                            onChange={filter(setSearch)}
                            placeholder="Título o instrucciones"
                            className="block min-h-11 w-full rounded-xl border border-line bg-white pr-3.5 pl-11 text-[15px] hover:border-ink-300"
                        />
                    </div>
                </div>
                <SelectField label="Grado" value={grado} onChange={filter(setGrado)}>
                    <option value="">Todos</option>
                    {(grados.data ?? []).map((g) => (
                        <option key={g.id} value={g.id}>
                            {g.nombre}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Asignatura" value={asignatura} onChange={filter(setAsignatura)}>
                    <option value="">Todas</option>
                    {(asignaturas.data ?? []).map((a) => (
                        <option key={a.id} value={a.id}>
                            {a.nombre}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Nivel" value={nivel} onChange={filter(setNivel)}>
                    <option value="">Todos</option>
                    {NIVELES.map((n) => (
                        <option key={n.value} value={n.value}>
                            {n.label}
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
            ) : items.length === 0 ? (
                <EmptyState icon={Library} title="No hay recursos con estos filtros">
                    Crea actividades de refuerzo para que el sistema pueda proponerlas a los estudiantes.
                </EmptyState>
            ) : (
                <>
                    <ListBox>
                        {items.map((r) => (
                            <li key={r.id} className="px-4 py-3 sm:px-5">
                                <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
                                    <div className="min-w-0 flex-1 basis-64">
                                        <p className="font-bold text-ink-900">{r.titulo}</p>
                                        <p className="text-sm text-ink-500">
                                            {r.grado_nombre} · {r.asignatura_nombre} · {r.tema_nombre}
                                        </p>
                                        <p className="mt-1.5 line-clamp-2 text-sm text-ink-700">{r.instrucciones}</p>
                                        <p className="mt-1.5 text-xs text-ink-500">
                                            {r.duracion_minutos ? `${r.duracion_minutos} min · ` : ''}
                                            Creado por {r.creado_por_nombre ?? 'el sistema'}
                                        </p>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Chip tone={NIVEL_TONE[r.nivel]}>{NIVEL_LABEL[r.nivel]}</Chip>
                                        <Chip>{ESTRATEGIA_LABEL[r.estrategia]}</Chip>
                                        {!r.is_active && <Chip tone="danger">Inactivo</Chip>}
                                    </div>
                                    {canEdit(r) && (
                                        <div className="ml-auto flex">
                                            <IconButton label={`Editar ${r.titulo}`} onClick={() => setForm({ item: r })}>
                                                <Pencil className="size-5" aria-hidden="true" />
                                            </IconButton>
                                            <IconButton
                                                label={`${r.is_active ? 'Desactivar' : 'Activar'} ${r.titulo}`}
                                                tone={r.is_active ? 'danger' : undefined}
                                                onClick={() => setToggle(r)}
                                            >
                                                <Power className="size-5" aria-hidden="true" />
                                            </IconButton>
                                        </div>
                                    )}
                                </div>
                            </li>
                        ))}
                    </ListBox>
                    <Pagination page={page} count={list.data.count} pageSize={PAGE_SIZE} onPage={setPage} />
                </>
            )}

            {form && <RecursoForm item={form.item} temas={temas.data ?? []} onClose={() => setForm(null)} />}
            <ToggleActiveDialog item={toggle} endpoint={ENDPOINT} name={toggle?.titulo} noun="recurso" onClose={() => setToggle(null)} />
        </>
    )
}
