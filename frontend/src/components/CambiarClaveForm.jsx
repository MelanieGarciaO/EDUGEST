import { useState } from 'react'

import { api, parseApiError } from '../api/client'
import { Alert, Button, PasswordField } from './ui'

const MIN = 10
const MAX = 128 // = MAX_CLAVE del backend

const enviarPorDefecto = async (body) => (await api.post('/security/auth/change-password/', body)).data

/**
 * Crea la contraseña nueva con una CLAVE TEMPORAL que el usuario recibió por correo
 * (o que vio en el recuperador). Lo usan el primer acceso, el recuperador y el Perfil.
 *
 * - `enviar(body)`: hace la petición; por defecto POST /auth/change-password/.
 *   body = { clave_temporal, new_password }.
 * - `temporalInicial`: valor precargado (el recuperador ya conoce la temporal).
 * - Llama a onSuccess(data) con la respuesta (tokens nuevos y usuario).
 */
export default function CambiarClaveForm({
    onSuccess,
    secondaryAction,
    enviar = enviarPorDefecto,
    temporalInicial = '',
    etiquetaTemporal = 'Contraseña temporal',
    hintTemporal = 'Es la contraseña temporal que te llegó por correo.',
    textoBoton = 'Guardar contraseña',
}) {
    const [form, setForm] = useState({ temporal: temporalInicial, nueva: '', repetir: '' })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const [loading, setLoading] = useState(false)

    const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

    async function onSubmit(e) {
        e.preventDefault()
        const local = {}
        if (!form.temporal.trim()) local.temporal = 'Escribe la clave temporal.'
        if (form.nueva.length < MIN) local.nueva = `Debe tener al menos ${MIN} caracteres.`
        else if (form.nueva.length > MAX) local.nueva = `Puede tener máximo ${MAX} caracteres.`
        else if (!form.nueva.trim()) local.nueva = 'La contraseña no puede ser solo espacios.'
        else if (form.nueva === form.temporal.trim()) local.nueva = 'La contraseña nueva debe ser distinta de la temporal.'
        if (form.repetir !== form.nueva) local.repetir = 'Las contraseñas no coinciden.'
        setErrors(local)
        setGeneral('')
        if (Object.keys(local).length) return

        setLoading(true)
        try {
            const data = await enviar({ clave_temporal: form.temporal.trim(), new_password: form.nueva })
            setLoading(false)
            onSuccess(data)
        } catch (err) {
            const { message, fields } = parseApiError(err)
            const detalle = err?.response?.data?.detail ?? message
            setLoading(false)

            // Venció mientras tenía la sesión abierta: ya le llegó otra y puede escribirla aquí mismo.
            if (err?.response?.data?.code === 'clave_temporal_vencida') {
                setForm((f) => ({ ...f, temporal: '' }))
                setErrors({ temporal: 'Escribe la nueva contraseña temporal que te acabamos de enviar.' })
                setGeneral(detalle)
                return
            }

            const mapped = {}
            if (fields.clave_temporal) mapped.temporal = fields.clave_temporal
            if (fields.new_password) mapped.nueva = fields.new_password
            setErrors(mapped)
            if (!Object.keys(mapped).length) setGeneral(detalle)
        }
    }

    return (
        <form onSubmit={onSubmit} noValidate>
            {general ? <Alert className="mb-4">{general}</Alert> : null}
            <PasswordField
                label={etiquetaTemporal}
                autoComplete="one-time-code"
                maxLength={MAX}
                value={form.temporal}
                onChange={set('temporal')}
                error={errors.temporal}
                hint={hintTemporal}
            />
            <PasswordField
                className="mt-4"
                label="Contraseña nueva"
                autoComplete="new-password"
                maxLength={MAX}
                value={form.nueva}
                onChange={set('nueva')}
                error={errors.nueva}
                hint={`Entre ${MIN} y ${MAX} caracteres. Evita datos personales y claves comunes.`}
            />
            <PasswordField
                className="mt-4"
                label="Repite la contraseña nueva"
                autoComplete="new-password"
                maxLength={MAX}
                value={form.repetir}
                onChange={set('repetir')}
                error={errors.repetir}
            />
            <div className="mt-6 flex flex-wrap gap-3">
                <Button type="submit" loading={loading}>
                    {textoBoton}
                </Button>
                {secondaryAction}
            </div>
        </form>
    )
}
