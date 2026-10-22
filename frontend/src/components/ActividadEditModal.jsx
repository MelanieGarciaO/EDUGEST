import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, parseApiError } from '../api/client'
import { horaCorta, hoyISO } from '../lib/dates'
import { MaterialesInput } from './Materiales'
import { Alert, Button, CheckboxField, Field, Modal, TextAreaField } from './ui'

/** Edita descripción, fecha, hora, materiales y tema de una actividad vigente. */
export default function ActividadEditModal({ actividad, onClose }) {
    const qc = useQueryClient()
    const [form, setForm] = useState(null)
    const [err, setErr] = useState({ message: '', fields: {} })

    useEffect(() => {
        if (actividad) {
            setForm({
                descripcion: actividad.descripcion,
                fecha_entrega: actividad.fecha_entrega,
                hora_entrega: horaCorta(actividad.hora_entrega),
                materiales: actividad.materiales ?? [],
                tema: actividad.tema ?? '',
                es_evaluacion_refuerzo: !!actividad.es_evaluacion_refuerzo,
            })
            setErr({ message: '', fields: {} })
        }
    }, [actividad])

    const save = useMutation({
        mutationFn: () => api.patch(`/activities/actividades/${actividad.id}/`, { ...form, hora_entrega: form.hora_entrega || null }),
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ['actividades'] })
            onClose()
        },
        onError: (e) => setErr(parseApiError(e)),
    })

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
    const f = err.fields

    return (
        <Modal
            open={!!actividad}
            onClose={onClose}
            title={actividad ? `Editar actividad de ${actividad.asignatura_nombre}` : ''}
            footer={
                <>
                    <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
                        Cancelar
                    </Button>
                    <Button onClick={() => save.mutate()} loading={save.isPending}>
                        Guardar cambios
                    </Button>
                </>
            }
        >
            {form && (
                <div className="space-y-4">
                    {err.message && !Object.keys(f).length && <Alert>{err.message}</Alert>}
                    <TextAreaField label="Descripción" value={form.descripcion} onChange={set('descripcion')} maxLength={2000} error={f.descripcion} />
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="Fecha de entrega" type="date" min={hoyISO()} value={form.fecha_entrega} onChange={set('fecha_entrega')} error={f.fecha_entrega} />
                        <Field label="Hora de entrega" type="time" value={form.hora_entrega} onChange={set('hora_entrega')} error={f.hora_entrega} hint="Opcional. Sin hora, la entrega vale todo el día." />
                    </div>
                    <Field label="Tema" value={form.tema} onChange={set('tema')} maxLength={150} error={f.tema} />
                    <MaterialesInput value={form.materiales} onChange={(v) => setForm((x) => ({ ...x, materiales: v }))} error={f.materiales} />
                    <CheckboxField
                        label="Es una evaluación de refuerzo"
                        hint="Su nota cerrará los planes de refuerzo completados de los estudiantes en el tema que califiques."
                        checked={form.es_evaluacion_refuerzo}
                        onChange={(e) => setForm((x) => ({ ...x, es_evaluacion_refuerzo: e.target.checked }))}
                    />
                </div>
            )}
        </Modal>
    )
}
