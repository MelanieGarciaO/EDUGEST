import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListTree, Pencil, Plus, Power } from 'lucide-react'

import { api, fetchAll, parseApiError } from '../../api/client'
import { ToggleActiveDialog } from '../../components/CrudForm'
import { IconButton, ListBox, Row } from '../../components/ListParts'
import {
    Alert,
    Button,
    Card,
    Chip,
    EmptyState,
    Field,
    Modal,
    PageHeader,
    SelectField,
    Spinner,
} from '../../components/ui'
import { useAsignaturasActivas, useGrados } from '../../lib/queries'

function TemaForm({ item, padre, grados, asignaturas, onClose }) {
    const queryClient = useQueryClient()
    const editing = Boolean(item)
    const locked = editing || Boolean(padre)
    const [values, setValues] = useState({
        grado: padre?.grado ?? '',
        asignatura: padre?.asignatura ?? '',
        nombre: item?.nombre ?? '',
    })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const set = (k) => (e) => setValues((v) => ({ ...v, [k]: e.target.value }))

    const save = useMutation({
        mutationFn: async (payload) =>
            editing
                ? (await api.patch(`/academic/temas/${item.id}/`, payload)).data
                : (await api.post('/academic/temas/', payload)).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['temas'] })
            onClose()
        },
        onError: (err) => {
            const { fields, message } = parseApiError(err)
            setErrors(fields)
            setGeneral(fields.padre ?? (Object.keys(fields).length ? '' : message))
        },
    })

    function onSubmit(e) {
        e.preventDefault()
        const local = {}
        if (!values.nombre.trim()) local.nombre = 'Escribe el nombre.'
        if (!locked) {
            if (!values.grado) local.grado = 'Elige el grado.'
            if (!values.asignatura) local.asignatura = 'Elige la asignatura.'
        }
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return
        const nombre = values.nombre.trim()
        save.mutate(
            editing
                ? { nombre }
                : { grado: Number(values.grado), asignatura: Number(values.asignatura), padre: padre?.id ?? null, nombre },
        )
    }

    const context = item ?? padre
    const title = editing ? (item.es_subtema ? 'Editar subtema' : 'Editar tema') : padre ? 'Nuevo subtema' : 'Nuevo tema'

    return (
        <Modal
            open
            onClose={onClose}
            title={title}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
                        Cancelar
                    </Button>
                    <Button type="submit" form="tema-form" loading={save.isPending}>
                        {editing ? 'Guardar cambios' : 'Crear'}
                    </Button>
                </>
            }
        >
            <form id="tema-form" onSubmit={onSubmit} noValidate className="space-y-4">
                {general && <Alert>{general}</Alert>}
                {locked ? (
                    <p className="rounded-xl bg-brand-50 px-4 py-3 text-sm text-ink-700">
                        {context.grado_nombre} · {context.asignatura_nombre}
                        {padre && (
                            <>
                                {' · '}
                                Dentro de <strong>{padre.nombre}</strong>
                            </>
                        )}
                        {item?.padre_nombre && (
                            <>
                                {' · '}
                                Dentro de <strong>{item.padre_nombre}</strong>
                            </>
                        )}
                    </p>
                ) : (
                    <div className="grid gap-4 sm:grid-cols-2">
                        <SelectField label="Grado" value={values.grado} onChange={set('grado')} error={errors.grado}>
                            <option value="">Elige un grado</option>
                            {grados.map((g) => (
                                <option key={g.id} value={g.id}>
                                    {g.nombre}
                                </option>
                            ))}
                        </SelectField>
                        <SelectField label="Asignatura" value={values.asignatura} onChange={set('asignatura')} error={errors.asignatura}>
                            <option value="">Elige una asignatura</option>
                            {asignaturas.map((a) => (
                                <option key={a.id} value={a.id}>
                                    {a.nombre}
                                </option>
                            ))}
                        </SelectField>
                    </div>
                )}
                <Field
                    label="Nombre"
                    placeholder={padre ? 'Ej.: Suma de fracciones' : 'Ej.: Fracciones'}
                    value={values.nombre}
                    onChange={set('nombre')}
                    error={errors.nombre}
                    hint={editing ? 'El grado, la asignatura y el tema padre no se pueden cambiar una vez creado.' : undefined}
                />
            </form>
        </Modal>
    )
}

function TemaActions({ t, onEdit, onToggle }) {
    return (
        <>
            <IconButton label={`Editar ${t.nombre}`} onClick={() => onEdit(t)}>
                <Pencil className="size-5" aria-hidden="true" />
            </IconButton>
            <IconButton
                label={`${t.is_active ? 'Desactivar' : 'Activar'} ${t.nombre}`}
                tone={t.is_active ? 'danger' : undefined}
                onClick={() => onToggle(t)}
            >
                <Power className="size-5" aria-hidden="true" />
            </IconButton>
        </>
    )
}

function TemaRows({ tema, subtemas, onAddSub, onEdit, onToggle }) {
    return (
        <>
            <Row
                title={tema.nombre}
                detail={`${tema.grado_nombre} · ${tema.asignatura_nombre}${tema.padre_nombre ? ` · Dentro de ${tema.padre_nombre}` : ''}`}
                chips={!tema.is_active && <Chip tone="danger">Inactivo</Chip>}
            >
                {!tema.padre && tema.is_active && (
                    <IconButton label={`Agregar subtema a ${tema.nombre}`} onClick={onAddSub}>
                        <Plus className="size-5" aria-hidden="true" />
                    </IconButton>
                )}
                <TemaActions t={tema} onEdit={onEdit} onToggle={onToggle} />
            </Row>
            {subtemas.map((s) => (
                <li
                    key={s.id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-1 border-l-4 border-brand-200 bg-brand-50/50 py-2.5 pr-4 pl-6 sm:pr-5 sm:pl-10"
                >
                    <p className="min-w-0 flex-1 basis-48 font-semibold text-ink-900">{s.nombre}</p>
                    {!s.is_active && <Chip tone="danger">Inactivo</Chip>}
                    <div className="ml-auto flex">
                        <TemaActions t={s} onEdit={onEdit} onToggle={onToggle} />
                    </div>
                </li>
            ))}
        </>
    )
}

export default function Temas() {
    const [grado, setGrado] = useState('')
    const [asignatura, setAsignatura] = useState('')
    const [estado, setEstado] = useState('true')
    const [form, setForm] = useState(null) // { item?, padre? }
    const [toggle, setToggle] = useState(null)

    const grados = useGrados()
    const asignaturas = useAsignaturasActivas()
    const params = { grado: grado || undefined, asignatura: asignatura || undefined, is_active: estado || undefined }
    const temas = useQuery({ queryKey: ['temas', 'admin', params], queryFn: () => fetchAll('/academic/temas/', params) })

    const items = temas.data ?? []
    const ids = new Set(items.map((t) => t.id))
    const roots = items.filter((t) => !t.padre || !ids.has(t.padre))
    const kids = (id) => items.filter((t) => t.padre === id)

    const ready = grados.data?.length && asignaturas.data?.length

    return (
        <>
            <PageHeader
                title="Temas"
                subtitle="Catálogo de temas y subtemas por grado y asignatura. Las notas y los refuerzos se organizan con él."
            >
                <Button onClick={() => setForm({})} disabled={!ready}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo tema
                </Button>
            </PageHeader>
            {!ready && !grados.isPending && !asignaturas.isPending && (
                <Alert tone="warn" className="mb-4">
                    Primero crea grados y asignaturas en «Estructura académica».
                </Alert>
            )}

            <Card className="mb-4 grid gap-4 sm:grid-cols-3">
                <SelectField label="Grado" value={grado} onChange={(e) => setGrado(e.target.value)}>
                    <option value="">Todos</option>
                    {(grados.data ?? []).map((g) => (
                        <option key={g.id} value={g.id}>
                            {g.nombre}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Asignatura" value={asignatura} onChange={(e) => setAsignatura(e.target.value)}>
                    <option value="">Todas</option>
                    {(asignaturas.data ?? []).map((a) => (
                        <option key={a.id} value={a.id}>
                            {a.nombre}
                        </option>
                    ))}
                </SelectField>
                <SelectField label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
                    <option value="true">Activos</option>
                    <option value="">Todos</option>
                </SelectField>
            </Card>

            {temas.isPending ? (
                <Spinner className="text-brand-600" />
            ) : temas.isError ? (
                <Alert>{parseApiError(temas.error).message}</Alert>
            ) : roots.length === 0 ? (
                <EmptyState icon={ListTree} title="No hay temas con estos filtros">
                    Crea los temas de cada asignatura para poder registrar notas y armar refuerzos.
                </EmptyState>
            ) : (
                <ListBox>
                    {roots.map((t) => (
                        <TemaRows
                            key={t.id}
                            tema={t}
                            subtemas={kids(t.id)}
                            onAddSub={() => setForm({ padre: t })}
                            onEdit={(x) => setForm({ item: x })}
                            onToggle={setToggle}
                        />
                    ))}
                </ListBox>
            )}

            {form && (
                <TemaForm
                    item={form.item}
                    padre={form.padre}
                    grados={grados.data ?? []}
                    asignaturas={asignaturas.data ?? []}
                    onClose={() => setForm(null)}
                />
            )}
            <ToggleActiveDialog
                item={toggle}
                endpoint="/academic/temas/"
                name={toggle?.nombre}
                noun={toggle?.es_subtema ? 'subtema' : 'tema'}
                onClose={() => setToggle(null)}
            />
        </>
    )
}
