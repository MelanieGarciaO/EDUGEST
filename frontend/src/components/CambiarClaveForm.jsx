import { useId, useState } from 'react'
import { CheckCircle2, Circle, XCircle } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { evaluarClave, MAX_CLAVE } from '../lib/clave'
import { Alert, Button, PasswordField } from './ui'

const enviarPorDefecto = async (body) => (await api.post('/security/auth/change-password/', body)).data

/**
 * Una regla de la lista: gris mientras no se cumple, verde al cumplirse y roja si se intentó
 * guardar sin cumplirla.
 */
function Regla({ ok, intento, children }) {
    const estado = ok ? 'ok' : intento ? 'error' : 'pendiente'
    const Icono = { ok: CheckCircle2, error: XCircle, pendiente: Circle }[estado]
    const color = { ok: 'text-ok-700', error: 'text-danger-600', pendiente: 'text-ink-500' }[estado]
    return (
        <li className={`flex items-start gap-2 text-sm transition-colors ${color} ${ok ? 'font-semibold' : ''}`}>
            <Icono className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
                {children}
                <span className="sr-only">{ok ? ' (cumplido)' : ' (pendiente)'}</span>
            </span>
        </li>
    )
}

/**
 * Crea la contraseña nueva con una CLAVE TEMPORAL que el usuario recibió por correo
 * (o que vio en el recuperador). Lo usan el primer acceso, el recuperador y el Perfil.
 *
 * - `enviar(body)`: hace la petición; por defecto POST /auth/change-password/.
 *   body = { clave_temporal, new_password }.
 * - `temporalInicial`: valor precargado (el recuperador ya conoce la temporal).
 * - `email`: correo del usuario cuando no hay sesión (recuperador), para la regla de datos personales.
 * - Llama a onSuccess(data) con la respuesta (tokens nuevos y usuario).
 *
 * Mientras se escribe, cada requisito de la contraseña cambia a verde al cumplirse
 * (lib/clave.js replica las reglas del backend).
 */
export default function CambiarClaveForm({
    onSuccess,
    secondaryAction,
    enviar = enviarPorDefecto,
    temporalInicial = '',
    email = '',
    etiquetaTemporal = 'Contraseña temporal',
    hintTemporal = 'Es la contraseña temporal que te llegó por correo.',
    textoBoton = 'Guardar contraseña',
}) {
    const { user } = useAuth()
    const idReglas = useId()
    const idCoinciden = useId()
    const [form, setForm] = useState({ temporal: temporalInicial, nueva: '', repetir: '' })
    const [errors, setErrors] = useState({})
    const [general, setGeneral] = useState('')
    const [loading, setLoading] = useState(false)
    const [intento, setIntento] = useState(false) // se intentó guardar: lo pendiente se marca en rojo

    const datos = [email, user?.email, user?.first_name, user?.last_name]
    const { reglas, valida } = evaluarClave(form.nueva, { temporal: form.temporal, datos })
    const coinciden = form.repetir.length > 0 && form.repetir === form.nueva

    const set = (k) => (e) => {
        const valor = e.target.value
        setForm((f) => ({ ...f, [k]: valor }))
        // El error del servidor de ese campo deja de aplicar en cuanto se corrige.
        const campo = k === 'repetir' ? 'repetir' : k
        if (errors[campo]) {
            setErrors((actuales) => {
                const resto = { ...actuales }
                delete resto[campo]
                return resto
            })
        }
    }

    async function onSubmit(e) {
        e.preventDefault()
        setIntento(true)
        setGeneral('')
        const local = {}
        if (!form.temporal.trim()) local.temporal = 'Escribe la clave temporal.'
        setErrors(local)
        if (Object.keys(local).length || !valida || !coinciden) return

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
                maxLength={MAX_CLAVE}
                value={form.temporal}
                onChange={set('temporal')}
                error={errors.temporal}
                hint={hintTemporal}
            />
            <PasswordField
                className="mt-4"
                label="Contraseña nueva"
                autoComplete="new-password"
                maxLength={MAX_CLAVE}
                value={form.nueva}
                onChange={set('nueva')}
                error={errors.nueva}
                describe={idReglas}
                aria-invalid={errors.nueva || (intento && !valida) ? 'true' : undefined}
            />
            <div className="mt-2 rounded-xl border border-line bg-brand-50/50 px-3.5 py-3">
                <p className="mb-2 text-xs font-bold tracking-wide text-ink-700 uppercase">Tu contraseña debe cumplir</p>
                <ul id={idReglas} className="space-y-1.5" aria-live="polite">
                    {reglas.map((r) => (
                        <Regla key={r.clave} ok={r.ok} intento={intento}>
                            {r.texto}
                        </Regla>
                    ))}
                </ul>
            </div>
            <PasswordField
                className="mt-4"
                label="Repite la contraseña nueva"
                autoComplete="new-password"
                maxLength={MAX_CLAVE}
                value={form.repetir}
                onChange={set('repetir')}
                error={errors.repetir}
                describe={idCoinciden}
                aria-invalid={intento && !coinciden ? 'true' : undefined}
            />
            <ul id={idCoinciden} className="mt-2" aria-live="polite">
                <Regla ok={coinciden} intento={intento}>
                    {coinciden ? 'Las contraseñas coinciden' : form.repetir ? 'Las contraseñas aún no coinciden' : 'Repite la misma contraseña'}
                </Regla>
            </ul>
            <div className="mt-6 flex flex-wrap gap-3">
                <Button type="submit" loading={loading}>
                    {textoBoton}
                </Button>
                {secondaryAction}
            </div>
        </form>
    )
}
