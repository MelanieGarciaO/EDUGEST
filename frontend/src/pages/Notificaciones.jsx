import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck, ChevronRight, ShieldCheck } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { Alert, Button, Card, CheckboxField, Chip, EmptyState, PageHeader, Spinner } from '../components/ui'

const TONOS = { SEGURIDAD: 'warn', ACTIVIDADES: 'brand', CALIFICACIONES: 'ok', REFUERZO: 'brand', RECORDATORIOS: 'warn' }

function cuando(fecha) {
    const d = new Date(fecha)
    const minutos = Math.round((Date.now() - d.getTime()) / 60000)
    if (minutos < 1) return 'Ahora'
    if (minutos < 60) return `Hace ${minutos} min`
    if (minutos < 24 * 60) return `Hace ${Math.round(minutos / 60)} h`
    return d.toLocaleDateString('es-EC', { day: '2-digit', month: 'short', year: 'numeric' })
}

function Preferencias() {
    const queryClient = useQueryClient()
    const prefs = useQuery({
        queryKey: ['notificaciones', 'preferencias'],
        queryFn: async () => (await api.get('/notifications/preferencias/')).data,
    })
    const guardar = useMutation({
        mutationFn: async (cambio) => (await api.patch('/notifications/preferencias/', cambio)).data,
        onSuccess: (data) => queryClient.setQueryData(['notificaciones', 'preferencias'], data),
    })

    return (
        <Card>
            <h2 className="text-lg font-extrabold text-navy-800">Avisos por correo</h2>
            <p className="mt-1 mb-4 text-sm text-ink-500">Elige qué avisos quieres recibir también en tu correo. En la app siempre los verás.</p>
            {prefs.isPending && <Spinner className="text-brand-600" />}
            {prefs.isError && <Alert>{parseApiError(prefs.error).message}</Alert>}
            {prefs.data && (
                <div className="space-y-3">
                    {prefs.data.disponibles.map(({ clave, nombre }) => (
                        <CheckboxField
                            key={clave}
                            label={nombre}
                            checked={Boolean(prefs.data[clave])}
                            disabled={guardar.isPending}
                            onChange={(e) => guardar.mutate({ [clave]: e.target.checked })}
                        />
                    ))}
                    <div className="flex items-start gap-2 rounded-xl bg-brand-50 p-3 text-sm text-ink-700">
                        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-brand-700" aria-hidden="true" />
                        Los avisos de seguridad de tu cuenta (códigos, contraseñas temporales y cambios de clave) siempre se envían.
                    </div>
                    {guardar.isError && <Alert>{parseApiError(guardar.error).message}</Alert>}
                </div>
            )}
        </Card>
    )
}

export default function Notificaciones() {
    const navigate = useNavigate()
    const queryClient = useQueryClient()
    const [soloNoLeidas, setSoloNoLeidas] = useState(false)

    const lista = useInfiniteQuery({
        queryKey: ['notificaciones', 'lista', soloNoLeidas],
        queryFn: async ({ pageParam }) =>
            (await api.get('/notifications/', { params: { page: pageParam, ...(soloNoLeidas ? { no_leidas: 'true' } : {}) } })).data,
        initialPageParam: 1,
        getNextPageParam: (ultima, todas) => (ultima.next ? todas.length + 1 : undefined),
    })
    const refrescar = () => queryClient.invalidateQueries({ queryKey: ['notificaciones'] })

    const leer = useMutation({
        mutationFn: async (id) => (await api.post(`/notifications/${id}/leer/`)).data,
        onSuccess: refrescar,
    })
    const leerTodas = useMutation({
        mutationFn: async () => (await api.post('/notifications/leer-todas/')).data,
        onSuccess: refrescar,
    })

    const items = lista.data?.pages.flatMap((p) => p.results) ?? []
    const hayNoLeidas = items.some((n) => !n.leida)

    function abrir(n) {
        if (!n.leida) leer.mutate(n.id)
        if (n.enlace) navigate(n.enlace)
    }

    return (
        <>
            <PageHeader title="Notificaciones" subtitle="Avisos sobre actividades, calificaciones, planes de refuerzo y tu cuenta.">
                <Button variant="secondary" onClick={() => leerTodas.mutate()} loading={leerTodas.isPending} disabled={!hayNoLeidas}>
                    <CheckCheck className="size-5" aria-hidden="true" />
                    Marcar todas como leídas
                </Button>
            </PageHeader>

            <div className="grid gap-5 lg:grid-cols-[1fr_20rem]">
                <Card className="p-0">
                    <div className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm">
                        {[['Todas', false], ['No leídas', true]].map(([texto, valor]) => (
                            <button
                                key={texto}
                                type="button"
                                onClick={() => setSoloNoLeidas(valor)}
                                aria-pressed={soloNoLeidas === valor}
                                className={`rounded-full px-3 py-1 font-bold ${soloNoLeidas === valor ? 'bg-brand-100 text-navy-800' : 'text-ink-500 hover:bg-brand-50'}`}
                            >
                                {texto}
                            </button>
                        ))}
                    </div>
                    {lista.isPending && <div className="p-6"><Spinner className="text-brand-600" /></div>}
                    {lista.isError && <Alert className="m-5">{parseApiError(lista.error).message}</Alert>}
                    {lista.isSuccess && !items.length && (
                        <div className="p-6">
                            <EmptyState icon={Bell} title={soloNoLeidas ? 'No tienes avisos sin leer' : 'Aún no tienes notificaciones'}>
                                Aquí verás los avisos de EduGest.
                            </EmptyState>
                        </div>
                    )}
                    <ul>
                        {items.map((n) => (
                            <li key={n.id} className="border-b border-line last:border-0">
                                <button
                                    type="button"
                                    onClick={() => abrir(n)}
                                    className={`flex w-full items-start gap-3 px-5 py-4 text-left hover:bg-brand-50 ${n.leida ? '' : 'bg-brand-50/60'}`}
                                >
                                    <span className={`mt-2 size-2 shrink-0 rounded-full ${n.leida ? 'bg-transparent' : 'bg-brand-600'}`} aria-hidden="true" />
                                    <span className="min-w-0 flex-1">
                                        <span className="flex flex-wrap items-center gap-2">
                                            <span className={`text-[15px] ${n.leida ? 'font-medium text-ink-700' : 'font-extrabold text-navy-800'}`}>{n.titulo}</span>
                                            <Chip tone={TONOS[n.categoria]}>{n.categoria_nombre}</Chip>
                                        </span>
                                        <span className="mt-0.5 block text-sm text-ink-500">{n.mensaje}</span>
                                        <span className="mt-1 block text-xs text-ink-500">
                                            {cuando(n.created_at)}
                                            {!n.leida && <span className="sr-only"> · sin leer</span>}
                                        </span>
                                    </span>
                                    {n.enlace && <ChevronRight className="mt-1 size-5 shrink-0 text-ink-300" aria-hidden="true" />}
                                </button>
                            </li>
                        ))}
                    </ul>
                    {lista.hasNextPage && (
                        <div className="border-t border-line p-4 text-center">
                            <Button variant="ghost" onClick={() => lista.fetchNextPage()} loading={lista.isFetchingNextPage}>
                                Ver más
                            </Button>
                        </div>
                    )}
                </Card>
                <div>
                    <Preferencias />
                </div>
            </div>
        </>
    )
}
