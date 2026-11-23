import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, MailWarning, Pencil, Plus, Search, Send, UserCheck, UserX, Users as UsersIcon } from 'lucide-react'

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
import ExportarExcel from '../../components/ExportarExcel'
import ImportarExcel from '../../components/ImportarExcel'

const PAGE_SIZE = 20
const ROLE_OPTIONS = Object.entries(ROLE_LABELS)
const ROLE_TONE = { ADMINISTRADOR: 'warn', DOCENTE: 'brand', REPRESENTANTE: 'ok' }
const vencida = (u) => Boolean(u.clave_temporal_expira_en) && new Date(u.clave_temporal_expira_en) <= new Date()

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
            onSaved(data, !editing)
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
                    <Field
                        label="Nombres"
                        value={form.first_name}
                        onChange={set('first_name')}
                        error={errors.first_name}
                        maxLength={150}
                        autoComplete="off"
                        hint="Solo letras, sin números ni símbolos."
                    />
                    <Field
                        label="Apellidos"
                        value={form.last_name}
                        onChange={set('last_name')}
                        error={errors.last_name}
                        maxLength={150}
                        autoComplete="off"
                        hint="Solo letras, sin números ni símbolos."
                    />
                </div>
                <Field
                    label="Correo electrónico"
                    type="email"
                    value={form.email}
                    onChange={set('email')}
                    error={errors.email}
                    maxLength={254}
                    autoComplete="off"
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
                        El sistema enviará una contraseña temporal al correo del usuario, válida por 2 horas. Con ella
                        ingresará por primera vez y creará su propia contraseña. Tú no verás la contraseña.
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
    const [reenviar, setReenviar] = useState(null) // usuario al que se reenvía el acceso
    const [aviso, setAviso] = useState(null) // { tone, texto } tras crear o reenviar
    const debounced = useDebouncedValue(search)

    const params = { page, search: debounced || undefined, role: role || undefined, is_active: estado || undefined }
    const list = useQuery({
        queryKey: ['users', params],
        queryFn: async () => (await api.get('/security/users/', { params })).data,
        placeholderData: (previous) => previous,
        // Mientras haya correos de acceso en cola (importación), la lista se actualiza sola.
        refetchInterval: (query) => (query.state.data?.results?.some((u) => u.correo_acceso === 'EN_COLA') ? 5000 : false),
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

    const reenviarMutation = useMutation({
        mutationFn: async (u) => (await api.post(`/security/users/${u.id}/reenviar-acceso/`)).data,
        onSuccess: (data) => {
            setReenviar(null)
            setAviso({ tone: 'ok', texto: data.detail })
            refresh()
        },
        onError: () => refresh(), // el estado del correo quedó registrado como error
    })

    const filter = (setter) => (e) => {
        setter(e.target.value)
        setPage(1)
    }

    const users = list.data?.results ?? []

    return (
        <>
            <PageHeader title="Usuarios" subtitle="Crea y administra las cuentas de docentes, representantes y administradores.">
                <div className="flex flex-wrap items-start gap-2">
                    <ExportarExcel url="/security/users/exportar/" params={{ ...params, page: undefined }} archivo="usuarios.xlsx" />
                    <ImportarExcel
                        endpoint="/security/users/"
                        titulo="Importar usuarios"
                        columnas={[
                            { campo: 'nombres', titulo: 'Nombres' },
                            { campo: 'apellidos', titulo: 'Apellidos' },
                            { campo: 'correo', titulo: 'Correo' },
                            { campo: 'rol', titulo: 'Rol' },
                        ]}
                        notaExito="Cada usuario recibirá su propia contraseña temporal por correo. Los correos se envían en cola durante los próximos minutos; puedes seguir el avance en la lista («Correo en cola»)."
                    />
                    <Button onClick={() => setForm({})}>
                        <Plus className="size-5" aria-hidden="true" />
                        Nuevo usuario
                    </Button>
                </div>
            </PageHeader>

            {aviso && (
                <Alert tone={aviso.tone} className="mb-4">
                    {aviso.texto}
                </Alert>
            )}

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
                                            <span>{u.full_name}</span>
                                            {isSelf ? <span className="font-medium text-ink-500"> (tú)</span> : null}
                                        </p>
                                        <p className="truncate text-sm text-ink-500">{u.email}</p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Chip tone={ROLE_TONE[u.role]}>{ROLE_LABELS[u.role]}</Chip>
                                        {!u.is_active && <Chip tone="danger">Inactivo</Chip>}
                                        {u.is_active && u.acceso_pendiente && u.correo_acceso === 'ERROR' && (
                                            <span title="El correo con la contraseña temporal no se pudo enviar. Revisa la dirección y reenvía el acceso.">
                                                <Chip tone="danger">
                                                    <MailWarning className="mr-1 inline size-3.5" aria-hidden="true" />
                                                    Correo no enviado
                                                </Chip>
                                            </span>
                                        )}
                                        {u.is_active && u.acceso_pendiente && u.correo_acceso === 'EN_COLA' && (
                                            <span title="Usuario importado: su correo con la contraseña temporal está en la cola de envío.">
                                                <Chip tone="brand">
                                                    <Clock className="mr-1 inline size-3.5" aria-hidden="true" />
                                                    Correo en cola
                                                </Chip>
                                            </span>
                                        )}
                                        {u.is_active && u.acceso_pendiente && !['ERROR', 'EN_COLA'].includes(u.correo_acceso) && (
                                            <span
                                                title={
                                                    vencida(u)
                                                        ? 'Su contraseña temporal venció. Cuando intente ingresar con ella, el sistema le enviará otra por correo.'
                                                        : 'Aún no ingresa con la contraseña temporal que recibió por correo.'
                                                }
                                            >
                                                <Chip tone="warn">
                                                    {vencida(u)
                                                        ? 'Sin activar · clave vencida'
                                                        : u.clave_temporal_expira_en
                                                          ? `Sin activar · vence ${new Date(u.clave_temporal_expira_en).toLocaleString('es-EC', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}`
                                                          : 'Sin activar'}
                                                </Chip>
                                            </span>
                                        )}
                                    </div>
                                    <div className="ml-auto flex">
                                        <IconButton label={`Editar a ${u.full_name}`} onClick={() => setForm({ user: u })}>
                                            <Pencil className="size-5" aria-hidden="true" />
                                        </IconButton>
                                        {!isSelf && u.is_active && u.acceso_pendiente && (
                                            <IconButton label={`Reenviar acceso a ${u.full_name}`} onClick={() => setReenviar(u)}>
                                                <Send className="size-5" aria-hidden="true" />
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
                    onSaved={(data, creado) => {
                        setForm(null)
                        if (!creado) return
                        setAviso(
                            data.correo_acceso === 'ERROR'
                                ? { tone: 'warn', texto: `Se creó la cuenta de ${data.full_name}, pero no se pudo enviar el correo a ${data.email}. Revisa la dirección y usa «Reenviar acceso».` }
                                : { tone: 'ok', texto: `Se creó la cuenta de ${data.full_name}. Le enviamos la contraseña temporal a ${data.email}; vence en 2 horas y, si vence, recibirá otra al intentar ingresar.` },
                        )
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
                <span>
                    {toggle?.is_active
                        ? `${toggle?.full_name} ya no podrá iniciar sesión. Sus datos se conservan y puedes activarlo de nuevo cuando quieras.`
                        : `${toggle?.full_name} podrá volver a iniciar sesión con su contraseña actual.`}
                </span>
            </ConfirmDialog>

            <ConfirmDialog
                open={Boolean(reenviar)}
                title="Reenviar acceso"
                tone="primary"
                confirmLabel="Enviar correo"
                loading={reenviarMutation.isPending}
                error={reenviarMutation.isError ? parseApiError(reenviarMutation.error).message : ''}
                onConfirm={() => reenviarMutation.mutate(reenviar)}
                onClose={() => {
                    setReenviar(null)
                    reenviarMutation.reset()
                }}
            >
                <span>
                    {`Se enviará a ${reenviar?.email ?? ''} un correo con una contraseña temporal nueva; la anterior dejará de funcionar. Solo es posible mientras ${reenviar?.full_name ?? 'el usuario'} no haya activado su cuenta.`}
                </span>
            </ConfirmDialog>
        </>
    )
}
