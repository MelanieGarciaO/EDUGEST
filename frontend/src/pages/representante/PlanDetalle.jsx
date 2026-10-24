import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, ClipboardCheck } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { PlanHeader, PlanTemas } from '../../components/PlanView'
import { Alert, Button, Card, ConfirmDialog, PageHeader, Spinner } from '../../components/ui'
import { usePlan } from '../../lib/queries'

export default function RepresentantePlanDetalle() {
    const { id } = useParams()
    const qc = useQueryClient()
    const { data: plan, isLoading, isError } = usePlan(id)
    const [marcando, setMarcando] = useState(null)

    const cumplir = useMutation({
        mutationFn: async (actividad) => (await api.post(`/reinforcement/actividades/${actividad.id}/cumplir/`)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plan', id] })
            qc.invalidateQueries({ queryKey: ['planes'] })
            setMarcando(null)
        },
    })

    const revisar = useMutation({
        mutationFn: async () => (await api.post(`/reinforcement/planes/${id}/revisar/`)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['plan', id] })
            qc.invalidateQueries({ queryKey: ['planes'] })
        },
    })

    const enCurso = plan?.estado === 'APROBADA'
    const puedeConfirmar = ['APROBADA', 'COMPLETADA'].includes(plan?.estado) && !plan?.revisado_en
    const acciones = (a) =>
        enCurso && a.estado === 'PENDIENTE' ? (
            <Button variant="ok" className="min-h-9 px-3 text-sm" onClick={() => { cumplir.reset(); setMarcando(a) }} aria-label={`Marcar como cumplida ${a.titulo}`}>
                <CheckCircle2 className="size-4" aria-hidden="true" />
                Marcar como cumplida
            </Button>
        ) : null

    return (
        <>
            <Link to="/representante/planes" className="mb-4 inline-flex items-center gap-1.5 text-sm font-bold text-brand-700 hover:underline">
                <ArrowLeft className="size-4" aria-hidden="true" />
                Volver a planes
            </Link>
            <PageHeader title="Plan de refuerzo" />

            {isLoading && <Spinner />}
            {isError && <Alert>No se encontró el plan o no tienes acceso a él.</Alert>}
            {plan && (
                <div className="max-w-3xl space-y-5">
                    {enCurso && (
                        <Alert tone="ok">Realiza estas actividades con {plan.estudiante_nombre} y márcalas como cumplidas. El docente verá el avance.</Alert>
                    )}
                    {plan.estado === 'COMPLETADA' && <Alert tone="ok">¡Plan completado! Todas las actividades fueron cumplidas.</Alert>}
                    {plan.estado === 'CANCELADA' && <Alert tone="warn">El docente canceló este plan.</Alert>}
                    <PlanHeader plan={plan} />
                    {puedeConfirmar ? (
                        <Card className="flex flex-wrap items-center justify-between gap-3">
                            <div className="min-w-0 flex-1 basis-60">
                                <p className="font-bold text-navy-800">¿Ya revisaste este plan?</p>
                                <p className="text-sm text-ink-500">
                                    {`Confirma que leíste el plan con ${plan.estudiante_nombre}. El docente verá tu confirmación.`}
                                </p>
                                {revisar.isError ? (
                                    <p className="mt-1 text-sm font-medium text-danger-600">{parseApiError(revisar.error).message}</p>
                                ) : null}
                            </div>
                            <Button variant="ok" onClick={() => revisar.mutate()} loading={revisar.isPending}>
                                <ClipboardCheck className="size-4" aria-hidden="true" />
                                Plan revisado
                            </Button>
                        </Card>
                    ) : null}
                    <PlanTemas plan={plan} actions={acciones} />
                </div>
            )}

            <ConfirmDialog
                open={!!marcando}
                title="¿Marcar la actividad como cumplida?"
                confirmLabel="Marcar como cumplida"
                tone="ok"
                loading={cumplir.isPending}
                error={cumplir.isError ? parseApiError(cumplir.error).message : null}
                onConfirm={() => cumplir.mutate(marcando)}
                onClose={() => setMarcando(null)}
            >
                «{marcando?.titulo}». Si te equivocas, el docente puede reabrirla.
            </ConfirmDialog>
        </>
    )
}
