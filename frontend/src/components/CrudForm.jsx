import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { api, parseApiError } from '../api/client'
import { Alert, Button, ConfirmDialog, Field, Modal, SelectField } from './ui'

/**
 * Formulario de alta/edición genérico para el catálogo académico.
 * fields: [{ name, label, type?: 'text'|'number'|'select', options?: [{value,label}], hint?, upper? }]
 */
export function CrudForm({ title, endpoint, entity, fields, extra, onClose, submitLabel = 'Guardar' }) {
    const queryClient = useQueryClient()
    const editing = Boolean(entity)
    const [values, setValues] = useState(() =>
        Object.fromEntries(fields.map((f) => [f.name, entity?.[f.name] ?? f.initial ?? ''])),
    )
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')

    const save = useMutation({
        mutationFn: async (payload) =>
            editing ? (await api.patch(`${endpoint}${entity.id}/`, payload)).data : (await api.post(endpoint, payload)).data,
        onSuccess: () => {
            queryClient.invalidateQueries()
            onClose()
        },
        onError: (err) => {
            const { fields: serverFields, message } = parseApiError(err)
            setErrors(serverFields)
            // DRF redacta así los duplicados de varios campos; se reemplaza por un texto claro.
            setGeneral(
                Object.keys(serverFields).length
                    ? ''
                    : /conjunto único/.test(message)
                        ? 'Ya existe un registro con esos mismos datos.'
                        : message,
            )
        },
    })

    function onSubmit(e) {
        e.preventDefault()
        const local = {}
        const payload = { ...extra }
        for (const f of fields) {
            let v = values[f.name]
            if (typeof v === 'string') v = v.trim()
            if (v === '' || v == null) {
                local[f.name] = f.type === 'select' ? 'Elige una opción.' : 'Completa este campo.'
            }
            payload[f.name] = f.type === 'number' || f.type === 'select' ? (v === '' ? v : Number(v)) : v
        }
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return
        save.mutate(payload)
    }

    const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }))

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
                    <Button type="submit" form="crud-form" loading={save.isPending}>
                        {submitLabel}
                    </Button>
                </>
            }
        >
            <form id="crud-form" onSubmit={onSubmit} noValidate className="space-y-4">
                {general && <Alert>{general}</Alert>}
                {fields.map((f) =>
                    f.type === 'select' ? (
                        <SelectField
                            key={f.name}
                            label={f.label}
                            value={values[f.name]}
                            onChange={set(f.name)}
                            error={errors[f.name]}
                            hint={f.hint}
                        >
                            <option value="">Elige una opción…</option>
                            {f.options.map((o) => (
                                <option key={o.value} value={o.value}>
                                    {o.label}
                                </option>
                            ))}
                        </SelectField>
                    ) : (
                        <Field
                            key={f.name}
                            label={f.label}
                            type={f.type === 'number' ? 'number' : 'text'}
                            min={f.min}
                            max={f.max}
                            value={values[f.name]}
                            onChange={set(f.name)}
                            error={errors[f.name]}
                            hint={f.hint}
                        />
                    ),
                )}
            </form>
        </Modal>
    )
}

/** Confirma activar o desactivar un registro (PATCH is_active). */
export function ToggleActiveDialog({ item, endpoint, name, noun, onClose }) {
    const queryClient = useQueryClient()
    const deactivating = item?.is_active
    const toggle = useMutation({
        mutationFn: () => api.patch(`${endpoint}${item.id}/`, { is_active: !item.is_active }),
        onSuccess: () => {
            queryClient.invalidateQueries()
            onClose()
        },
    })

    return (
        <ConfirmDialog
            open={Boolean(item)}
            title={deactivating ? `Desactivar ${noun}` : `Activar ${noun}`}
            tone={deactivating ? 'danger' : 'ok'}
            confirmLabel={deactivating ? 'Desactivar' : 'Activar'}
            loading={toggle.isPending}
            error={toggle.isError ? parseApiError(toggle.error).message : ''}
            onConfirm={() => toggle.mutate()}
            onClose={() => {
                toggle.reset()
                onClose()
            }}
        >
            {deactivating
                ? `«${name}» dejará de estar disponible para nuevas asignaciones. Sus datos se conservan.`
                : `«${name}» volverá a estar disponible.`}
        </ConfirmDialog>
    )
}
