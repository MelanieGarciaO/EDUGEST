import { useState } from 'react'

import { api, parseApiError } from '../api/client'
import { Alert, Button, PasswordField } from './ui'

const MIN = 10
const VACIO = { actual: '', nueva: '', repetir: '' }

/**
 * Formulario de cambio de contraseña (lo usan el primer acceso y el Perfil).
 * Llama a onSuccess(data) con la respuesta del servidor (tokens nuevos y usuario).
 */
export default function CambiarClaveForm({ forced = false, onSuccess, secondaryAction }) {
    const [form, setForm] = useState(VACIO)
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const [loading, setLoading] = useState(false)

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

    async function onSubmit(e) {
        e.preventDefault()
        const local = {}
        if (!form.actual) local.actual = 'Escribe tu contraseña actual.'
        if (form.nueva.length < MIN) local.nueva = `Debe tener al menos ${MIN} caracteres.`
        else if (form.nueva === form.actual) local.nueva = 'La contraseña nueva debe ser distinta de la actual.'
        if (form.repetir !== form.nueva) local.repetir = 'Las contraseñas no coinciden.'
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return

        setLoading(true)
        try {
            const { data } = await api.post('/security/auth/change-password/', {
                old_password: form.actual,
                new_password: form.nueva,
            })
            setForm(VACIO)
            setLoading(false)
            onSuccess(data)
        } catch (err) {
            const { message, fields } = parseApiError(err)
            const mapped = {}
            if (fields.old_password) mapped.actual = fields.old_password
            if (fields.new_password) mapped.nueva = fields.new_password
            setErrors(mapped)
            if (!Object.keys(mapped).length) setGeneral(message)
            setLoading(false)
        }
    }

    return (
        <form onSubmit={onSubmit} noValidate>
            {general ? <Alert className="mb-4">{general}</Alert> : null}
            <PasswordField
                label="Contraseña actual"
                autoComplete="current-password"
                value={form.actual}
                onChange={set('actual')}
                error={errors.actual}
                hint={forced ? 'Es la contraseña temporal que recibiste.' : undefined}
            />
            <PasswordField
                className="mt-4"
                label="Contraseña nueva"
                autoComplete="new-password"
                value={form.nueva}
                onChange={set('nueva')}
                error={errors.nueva}
                hint={`Mínimo ${MIN} caracteres. Evita datos personales y claves comunes.`}
            />
            <PasswordField
                className="mt-4"
                label="Repite la contraseña nueva"
                autoComplete="new-password"
                value={form.repetir}
                onChange={set('repetir')}
                error={errors.repetir}
            />
            <div className="mt-6 flex flex-wrap gap-3">
                <Button type="submit" loading={loading}>
                    Guardar contraseña
                </Button>
                {secondaryAction}
            </div>
        </form>
    )
}
