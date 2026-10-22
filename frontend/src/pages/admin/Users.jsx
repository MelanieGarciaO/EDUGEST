import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, Pencil, Plus, Search, UserCheck, UserX, Users as UsersIcon } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import {
    Alert,
    Button,
    Card,
    Chip,
    ConfirmDialog,
    EmptyState,
    Field,
    Modal,
    PageHeader,
    Pagination,
    SelectField,
    Spinner,
} from '../../components/ui'
import { useDebouncedValue } from '../../lib/hooks'
import { ROLE_LABELS } from '../../lib/roles'

const PAGE_SIZE = 20
const ROLE_OPTIONS = Object.entries(ROLE_LABELS)
const ROLE_TONE = { ADMINISTRADOR: 'warn', DOCENTE: 'brand', REPRESENTANTE: 'ok' }

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

/** Muestra la contraseña temporal una sola vez, con botón para copiarla. */
function TemporaryPassword({ data, onClose }) {
    const [copied, setCopied] = useState(false)

    async function copy() {
        try {
            await navigator.clipboard.writeText(data.password)
            setCopied(true)
        } catch {
            setCopied(false)
        }
    }

    return (
        <Modal
            open={Boolean(data)}
            onClose={onClose}
            title={data?.title ?? ''}
            footer={<Button onClick={onClose}>Listo, ya la copié</Button>}
        >
            {data && (
                <>
                    <p className="text-ink-700">
                        Entrega esta contraseña temporal a <strong>{data.name}</strong>. Deberá cambiarla al iniciar sesión.
                    </p>
                    <div className="mt-4 flex items-center justify-between gap-3 rounded-xl bg-brand-50 px-4 py-3">
                        <code className="text-lg font-bold break-all text-navy-800">{data.password}</code>
                        <Button variant="secondary" className="min-h-10 shrink-0 px-3" onClick={copy}>
                            {copied ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                            {copied ? 'Copiada' : 'Copiar'}
                        </Button>
                    </div>
                    <Alert tone="warn" className="mt-4">
                        No se volverá a mostrar. Si la pierdes, deberás generar otra.
                    </Alert>
                </>
            )}
        </Modal>
    )
}

function UserForm({ user, isSelf, onClose, onSaved }) {
    const editing = Boolean(user)
    const queryClient = useQueryClient()
    const [form, setForm] = useState({
        first_name: user?.first_name ?? '',
        last_name: user?.last_name ?? '',
        email: user?.email ?? '',
        role: user?.role ?? 'DOCENTE',
    })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

    const save = useMutation({
        mutationFn: async (payload) =>
            editing
                ? (await api.patch(`/security/users/${user.id}/`, payload)).data
                : (await api.post('/security/users/', payload)).data,
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['users'] })
            queryClient.invalidateQueries({ queryKey: ['count'] })
            onSaved(data)
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
        if (!form.first_name.trim()) local.first_name = 'Escribe el nombre.'
        if (!form.last_name.trim()) local.last_name = 'Escribe el apellido.'
        if (!form.email.trim()) local.email = 'Escribe el correo electrónico.'
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return
        save.mutate({
            first_name: form.first_name.trim(),
            last_name: form.last_name.trim(),
            email: form.email.trim(),
            role: form.role,
        })
    }

    return (
        <Modal
            open
            onClose={onClose}
            title={editing ? 'Editar usuario' : 'Nuevo usuario'}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
                        Cancelar
                    </Button>
                    <Button type="submit" form="user-form" loading={save.isPending}>
                        {editing ? 'Guardar cambios' : 'Crear usuario'}
                    </Button>
                </>
            }
        >
            <form id="user-form" onSubmit={onSubmit} noValidate className="space-y-4">
                {general && <Alert>{general}</Alert>}
                <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Nombres" value={form.first_name} onChange={set('first_name')} error={errors.first_name} />
                    <Field label="Apellidos" value={form.last_name} onChange={set('last_name')} error={errors.last_name} />
                </div>
                <Field
                    label="Correo electrónico"
                    type="email"
                    value={form.email}
                    onChange={set('email')}
                    error={errors.email}
                />
                <SelectField
                    label="Rol"
                    value={form.role}
                    onChange={set('role')}
                    error={errors.role}
                    disabled={isSelf}
                    hint={isSelf ? 'No puedes cambiar tu propio rol.' : undefined}
                >
                    {ROLE_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                            {label}
                        </option>
                    ))}
                </SelectField>
                {!editing && (
                    <p className="text-sm text-ink-500">
                        Al crear el usuario se generará una contraseña temporal que verás una sola vez.
                    </p>
                )}
            </form>
        </Modal>
    )
}

export default function Users() {
    const { user: me } = useAuth()
    const queryClient = useQueryClient()
    const [search, setSearch] = useState('')
    const [role, setRole] = useState('')
    const [estado, setEstado] = useState('true')
    const [page, setPage] = useState(1)
    const [form, setForm] = useState(null) // null | { user? }
    const [toggle, setToggle] = useState(null) // usuario a activar/desactivar
    const [reset, setReset] = useState(null) // usuario a restablecer
    const [temp, setTemp] = useState(null) // contraseña temporal a mostrar
    const debounced = useDebouncedValue(search)

    const params = { page, search: debounced || undefined, role: role || undefined, is_active: estado || undefined }
    const list = useQuery({
        queryKey: ['users', params],
        queryFn: async () => (await api.get('/security/users/', { params })).data,
        placeholderData: (previous) => previous,
    })

    const refresh = () => {
        queryClient.invalidateQueries({ queryKey: ['users'] })
        queryClient.invalidateQueries({ queryKey: ['count'] })
    }

    const toggleMutation = useMutation({
        mutationFn: (u) => api.post(`/security/users/${u.id}/${u.is_active ? 'deactivate' : 'activate'}/`),
        onSuccess: () => {
            refresh()
            setToggle(null)
        },
    })

    const resetMutation = useMutation({
        mutationFn: async (u) => (await api.post(`/security/users/${u.id}/reset-password/`)).data,
        onSuccess: (data, u) => {
            setReset(null)
            setTemp({ title: 'Contraseña restablecida', name: `${u.first_name} ${u.last_name}`, password: data.temporary_password })
        },
    })

    const filter = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    const users = list.data?.results ?? []

    return (
        <>
            <PageHeader title="Usuarios" subtitle="Crea y administra las cuentas de docentes, representantes y administradores.">
                <Button onClick={() => setForm({})}>
                    <Plus className="size-5" aria-hidden="true" />
                    Nuevo usuario
                </Button>
            </PageHeader>

            <Card className="mb-4 grid gap-4 sm:grid-cols-[1fr_12rem_12rem]">
                <div>
                    <label htmlFor="buscar" className="mb-1.5 block text-sm font-bold text-ink-700">
                        Buscar
                    </label>
                    <div className="relative">
                        <Search className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-ink-300" aria-hidden="true" />
                        <input
                            id="buscar"
                            type="search"
                            value={search}
                            onChange={filter(setSearch)}
                            placeholder="Nombre, apellido o correo"
                            className="block min-h-11 w-full rounded-xl border border-line bg-white pr-3.5 pl-11 text-[15px] hover:border-ink-300"
                        />
                    </div>
                </div>
                <SelectField label="Rol" value={role} onChange={filter(setRole)}>
                    <option value="">Todos</option>
                    {ROLE_OPTIONS.map(([value, label]) => (
                        <option key={value} value={value}>
                            {label}
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
            ) : users.length === 0 ? (
                <EmptyState icon={UsersIcon} title="No hay usuarios con estos filtros">
                    Cambia la búsqueda o crea un usuario nuevo.
                </EmptyState>
            ) : (
                <>
                    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-white">
                        {users.map((u) => {
                            const isSelf = u.id === me.id
                            return (
                                <li key={u.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-5">
                                    <div className="min-w-0 flex-1 basis-56">
                                        <p className="truncate font-bold text-ink-900">
                                            {u.full_name} {isSelf && <span className="font-medium text-ink-500">(tú)</span>}
                                        </p>
                                        <p className="truncate text-sm text-ink-500">{u.email}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Chip tone={ROLE_TONE[u.role]}>{ROLE_LABELS[u.role]}</Chip>
                                        {!u.is_active && <Chip tone="danger">Inactivo</Chip>}
                                        {u.is_active && u.must_change_password && <Chip tone="warn">Clave temporal</Chip>}
                                    </div>
                                    <div className="ml-auto flex">
                                        <IconButton label={`Editar a ${u.full_name}`} onClick={() => setForm({ user: u })}>
                                            <Pencil className="size-5" aria-hidden="true" />
                                        </IconButton>
                                        {!isSelf && u.is_active && (
                                            <IconButton label={`Restablecer contraseña de ${u.full_name}`} onClick={() => setReset(u)}>
                                                <KeyRound className="size-5" aria-hidden="true" />
                                            </IconButton>
                                        )}
                                        {!isSelf &&
                                            (u.is_active ? (
                                                <IconButton label={`Desactivar a ${u.full_name}`} tone="danger" onClick={() => setToggle(u)}>
                                                    <UserX className="size-5" aria-hidden="true" />
                                                </IconButton>
                                            ) : (
                                                <IconButton label={`Activar a ${u.full_name}`} onClick={() => setToggle(u)}>
                                                    <UserCheck className="size-5" aria-hidden="true" />
                                                </IconButton>
                                            ))}
                                    </div>
                                </li>
                            )
                        })}
                    </ul>
                    <Pagination page={page} count={list.data.count} pageSize={PAGE_SIZE} onPage={setPage} />
                </>
            )}

            {form && (
                <UserForm
                    user={form.user}
                    isSelf={form.user?.id === me.id}
                    onClose={() => setForm(null)}
                    onSaved={(data) => {
                        setForm(null)
                        if (data.temporary_password) {
                            setTemp({
                                title: 'Usuario creado',
                                name: data.full_name,
                                password: data.temporary_password,
                            })
                        }
                    }}
                />
            )}

            <ConfirmDialog
                open={Boolean(toggle)}
                title={toggle?.is_active ? 'Desactivar usuario' : 'Activar usuario'}
                tone={toggle?.is_active ? 'danger' : 'ok'}
                confirmLabel={toggle?.is_active ? 'Desactivar' : 'Activar'}
                loading={toggleMutation.isPending}
                error={toggleMutation.isError ? parseApiError(toggleMutation.error).message : ''}
                onConfirm={() => toggleMutation.mutate(toggle)}
                onClose={() => {
                    setToggle(null)
                    toggleMutation.reset()
                }}
            >
                {toggle?.is_active
                    ? `${toggle?.full_name} ya no podrá iniciar sesión. Sus datos se conservan y puedes activarlo de nuevo cuando quieras.`
                    : `${toggle?.full_name} podrá volver a iniciar sesión con su contraseña actual.`}
            </ConfirmDialog>

            <ConfirmDialog
                open={Boolean(reset)}
                title="Restablecer contraseña"
                tone="primary"
                confirmLabel="Generar contraseña temporal"
                loading={resetMutation.isPending}
                error={resetMutation.isError ? parseApiError(resetMutation.error).message : ''}
                onConfirm={() => resetMutation.mutate(reset)}
                onClose={() => {
                    setReset(null)
                    resetMutation.reset()
                }}
            >
                Se generará una contraseña temporal para {reset?.full_name} y se cerrarán sus sesiones abiertas. Tendrá que
                cambiarla al ingresar.
            </ConfirmDialog>

            <TemporaryPassword data={temp} onClose={() => setTemp(null)} />
        </>
    )
}
