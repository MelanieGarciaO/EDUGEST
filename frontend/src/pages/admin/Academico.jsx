import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { BookOpen, Layers, Pencil, Plus, Power, School } from 'lucide-react'

import { fetchAll, parseApiError } from '../../api/client'
import { CrudForm, ToggleActiveDialog } from '../../components/CrudForm'
import { Alert, Button, Chip, EmptyState, PageHeader, SelectField, Spinner, Tabs } from '../../components/ui'

const TABS = [
    { id: 'grados', label: 'Grados' },
    { id: 'paralelos', label: 'Paralelos' },
    { id: 'asignaturas', label: 'Asignaturas' },
]

function IconButton({ label, onClick, children, tone }) {
    return (
        <button
            type="button"
            onClick={onClick}
            aria-label={label}
            title={label}
            className={
                'grid size-10 place-items-center rounded-xl hover:bg-brand-50 ' +
                (tone === 'danger' ? 'text-danger-600 hover:bg-danger-50' : 'text-ink-700')
            }
        >
            {children}
        </button>
    )
}

function Rows({ query, empty, children }) {
    if (query.isPending) return <Spinner className="text-brand-600" />
    if (query.isError) return <Alert>{parseApiError(query.error).message}</Alert>
    if (query.data.length === 0) return empty
    return <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-white">{children}</ul>
}

function Row({ title, detail, chips, children }) {
    return (
        <li className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
            <div className="min-w-0 flex-1 basis-48">
                <p className="font-bold text-ink-900">{title}</p>
                {detail && <p className="text-sm text-ink-500">{detail}</p>}
            </div>
            {chips}
            <div className="ml-auto flex">{children}</div>
        </li>
    )
}

function GradosPanel() {
    const [form, setForm] = useState(null)
    const grados = useQuery({ queryKey: ['grados'], queryFn: () => fetchAll('/academic/grados/') })
    const fields = [
        { name: 'nombre', label: 'Nombre', hint: 'Por ejemplo: Quinto EGB' },
        { name: 'orden', label: 'Posición en EGB', type: 'number', min: 1, max: 10, hint: 'Un número del 1 al 10.' },
    ]
    return (
        <>
            <div className="mb-4 flex justify-end">
                <Button onClick={() => setForm({})}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo grado
                </Button>
            </div>
            <Rows query={grados} empty={<EmptyState icon={Layers} title="Aún no hay grados">Crea el primer grado de EGB.</EmptyState>}>
                {grados.data?.map((g) => (
                    <Row key={g.id} title={g.nombre} detail={`Posición ${g.orden} de 10`}>
                        <IconButton label={`Editar ${g.nombre}`} onClick={() => setForm({ item: g })}>
                            <Pencil className="size-5" aria-hidden="true" />
                        </IconButton>
                    </Row>
                ))}
            </Rows>
            {form && (
                <CrudForm
                    title={form.item ? 'Editar grado' : 'Nuevo grado'}
                    endpoint="/academic/grados/"
                    entity={form.item}
                    fields={fields}
                    onClose={() => setForm(null)}
                />
            )}
        </>
    )
}

function ParalelosPanel() {
    const [form, setForm] = useState(null)
    const [toggle, setToggle] = useState(null)
    const [gradoId, setGradoId] = useState('')
    const grados = useQuery({ queryKey: ['grados'], queryFn: () => fetchAll('/academic/grados/') })
    const paralelos = useQuery({ queryKey: ['paralelos', 'admin'], queryFn: () => fetchAll('/academic/paralelos/') })

    const visibles = paralelos.data?.filter((p) => !gradoId || String(p.grado) === gradoId)
    const fields = [
        {
            name: 'grado',
            label: 'Grado',
            type: 'select',
            options: (grados.data ?? []).map((g) => ({ value: g.id, label: g.nombre })),
        },
        { name: 'nombre', label: 'Paralelo', hint: 'Una letra: A, B, C…' },
    ]

    return (
        <>
            <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
                <SelectField label="Filtrar por grado" value={gradoId} onChange={(e) => setGradoId(e.target.value)} className="w-full sm:w-64">
                    <option value="">Todos los grados</option>
                    {(grados.data ?? []).map((g) => (
                        <option key={g.id} value={g.id}>
                            {g.nombre}
                        </option>
                    ))}
                </SelectField>
                <Button onClick={() => setForm({})} disabled={!grados.data?.length}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo paralelo
                </Button>
            </div>
            <Rows
                query={{ ...paralelos, data: visibles }}
                empty={<EmptyState icon={School} title="No hay paralelos">Crea un paralelo para empezar a asignar estudiantes y docentes.</EmptyState>}
            >
                {visibles?.map((p) => (
                    <Row
                        key={p.id}
                        title={p.nombre_completo}
                        detail={`${p.estudiantes_count} ${p.estudiantes_count === 1 ? 'estudiante' : 'estudiantes'}`}
                        chips={!p.is_active && <Chip tone="danger">Inactivo</Chip>}
                    >
                        <IconButton label={`Editar ${p.nombre_completo}`} onClick={() => setForm({ item: p })}>
                            <Pencil className="size-5" aria-hidden="true" />
                        </IconButton>
                        <IconButton
                            label={`${p.is_active ? 'Desactivar' : 'Activar'} ${p.nombre_completo}`}
                            tone={p.is_active ? 'danger' : undefined}
                            onClick={() => setToggle(p)}
                        >
                            <Power className="size-5" aria-hidden="true" />
                        </IconButton>
                    </Row>
                ))}
            </Rows>
            {form && (
                <CrudForm
                    title={form.item ? 'Editar paralelo' : 'Nuevo paralelo'}
                    endpoint="/academic/paralelos/"
                    entity={form.item}
                    fields={fields}
                    onClose={() => setForm(null)}
                />
            )}
            <ToggleActiveDialog item={toggle} endpoint="/academic/paralelos/" name={toggle?.nombre_completo} noun="paralelo" onClose={() => setToggle(null)} />
        </>
    )
}

function AsignaturasPanel() {
    const [form, setForm] = useState(null)
    const [toggle, setToggle] = useState(null)
    const asignaturas = useQuery({ queryKey: ['asignaturas'], queryFn: () => fetchAll('/academic/asignaturas/') })
    const fields = [{ name: 'nombre', label: 'Nombre', hint: 'Por ejemplo: Matemática' }]

    return (
        <>
            <div className="mb-4 flex justify-end">
                <Button onClick={() => setForm({})}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nueva asignatura
                </Button>
            </div>
            <Rows query={asignaturas} empty={<EmptyState icon={BookOpen} title="Aún no hay asignaturas">Crea las asignaturas que se dictan en la institución.</EmptyState>}>
                {asignaturas.data?.map((a) => (
                    <Row key={a.id} title={a.nombre} chips={!a.is_active && <Chip tone="danger">Inactiva</Chip>}>
                        <IconButton label={`Editar ${a.nombre}`} onClick={() => setForm({ item: a })}>
                            <Pencil className="size-5" aria-hidden="true" />
                        </IconButton>
                        <IconButton
                            label={`${a.is_active ? 'Desactivar' : 'Activar'} ${a.nombre}`}
                            tone={a.is_active ? 'danger' : undefined}
                            onClick={() => setToggle(a)}
                        >
                            <Power className="size-5" aria-hidden="true" />
                        </IconButton>
                    </Row>
                ))}
            </Rows>
            {form && (
                <CrudForm
                    title={form.item ? 'Editar asignatura' : 'Nueva asignatura'}
                    endpoint="/academic/asignaturas/"
                    entity={form.item}
                    fields={fields}
                    onClose={() => setForm(null)}
                />
            )}
            <ToggleActiveDialog item={toggle} endpoint="/academic/asignaturas/" name={toggle?.nombre} noun="asignatura" onClose={() => setToggle(null)} />
        </>
    )
}

const PANELS = { grados: GradosPanel, paralelos: ParalelosPanel, asignaturas: AsignaturasPanel }

export default function Academico() {
    const [params, setParams] = useSearchParams()
    const current = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'grados'
    const Panel = PANELS[current]

    return (
        <>
            <PageHeader title="Estructura académica" subtitle="Grados, paralelos y asignaturas de la institución." />
            <Tabs tabs={TABS} value={current} onChange={(id) => setParams({ tab: id }, { replace: true })} label="Secciones" />
            <div role="tabpanel" id={`panel-${current}`} aria-labelledby={`tab-${current}`}>
                <Panel />
            </div>
        </>
    )
}
