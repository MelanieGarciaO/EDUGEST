import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Card, Logo, PasswordField } from '../components/ui'
import { homeFor } from '../lib/roles'

const MIN = 10

export default function ChangePassword() {
    const { user, applySession, logout } = useAuth()
    const navigate = useNavigate()
    const forced = user.must_change_password
    const [form, setForm] = useState({ actual: '', nueva: '', repetir: '' })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const [loading, setLoading] = useState(false)

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

    async function onSubmit(e) {
        e.preventDefault()
        const local = {}
        if (!form.actual) local.actual = 'Escribe tu contraseña actual.'
        if (form.nueva.length < MIN) local.nueva = `Debe tener al menos ${MIN} caracteres.`
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
            applySession(data)
            navigate(homeFor(data.user.role), { replace: true })
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

    const formulario = (
        <form onSubmit={onSubmit} noValidate>
            {general && <Alert className="mb-4">{general}</Alert>}
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
                {forced ? (
                    <Button variant="secondary" onClick={logout}>
                        Cerrar sesión
                    </Button>
                ) : (
                    <Button variant="secondary" onClick={() => navigate(-1)}>
                        Cancelar
                    </Button>
                )}
            </div>
        </form>
    )

    if (!forced) {
        return (
            <div className="max-w-md">
                <h1 className="mb-6 text-2xl font-extrabold tracking-tight text-navy-800">Cambiar contraseña</h1>
                <Card>{formulario}</Card>
            </div>
        )
    }

    return (
        <div className="grid min-h-screen place-items-center bg-brand-50 px-4 py-10">
            <div className="w-full max-w-md">
                <Logo className="mb-6" />
                <Card>
                    <h1 className="text-2xl font-extrabold tracking-tight text-navy-800">Crea tu contraseña</h1>
                    <p className="mt-1 mb-6 text-ink-500">
                        Hola, {user.first_name}. Por seguridad, cambia la contraseña temporal antes de continuar.
                    </p>
                    {formulario}
                </Card>
            </div>
        </div>
    )
}
