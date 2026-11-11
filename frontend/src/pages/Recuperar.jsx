import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Check, Copy, KeyRound, Mail, ShieldCheck } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Card, Field, Logo } from '../components/ui'

const CLAVE_TEMPORAL = 'edugest:clave-temporal' // la lee CambiarClaveForm
const ESPERA = 60

const PASOS = [
    { icon: Mail, texto: 'Correo' },
    { icon: ShieldCheck, texto: 'Código' },
    { icon: KeyRound, texto: 'Clave temporal' },
]

function Pasos({ actual }) {
    return (
        <ol className="mb-6 flex items-center gap-2 text-xs font-bold" aria-label="Pasos">
            {PASOS.map(({ icon: Icon, texto }, i) => (
                <li key={texto} className={`flex flex-1 items-center gap-1.5 ${i <= actual ? 'text-brand-700' : 'text-ink-300'}`} aria-current={i === actual ? 'step' : undefined}>
                    <span className={`grid size-7 shrink-0 place-items-center rounded-full ${i <= actual ? 'bg-brand-100' : 'bg-brand-50'}`}>
                        <Icon className="size-4" aria-hidden="true" />
                    </span>
                    {texto}
                </li>
            ))}
        </ol>
    )
}

/**
 * Recuperación de contraseña: correo -> código OTP de 6 dígitos -> contraseña temporal.
 * Con la temporal se inicia sesión y el sistema obliga a crear la contraseña nueva.
 */
export default function Recuperar() {
    const { login } = useAuth()
    const [paso, setPaso] = useState(0)
    const [email, setEmail] = useState('')
    const [codigo, setCodigo] = useState('')
    const [temporal, setTemporal] = useState('')
    const [aviso, setAviso] = useState('')
    const [error, setError] = useState('')
    const [cargando, setCargando] = useState(false)
    const [espera, setEspera] = useState(0)
    const [copiado, setCopiado] = useState(false)

    useEffect(() => {
        if (!espera) return undefined
        const t = setTimeout(() => setEspera((s) => s - 1), 1000)
        return () => clearTimeout(t)
    }, [espera])

    async function solicitar(e) {
        e?.preventDefault()
        setError('')
        if (!/^\S+@\S+\.\S+$/.test(email.trim())) {
            setError('Escribe un correo electrónico válido.')
            return
        }
        setCargando(true)
        try {
            const { data } = await api.post('/security/auth/recuperar/solicitar/', { email: email.trim() })
            setAviso(data.detail)
            setPaso(1)
            setEspera(ESPERA)
        } catch (err) {
            const { fields, message } = parseApiError(err)
            setError(err?.response?.data?.detail ?? fields.email ?? message)
        } finally {
            setCargando(false)
        }
    }

    async function verificar(e) {
        e.preventDefault()
        setError('')
        setCargando(true)
        try {
            const { data } = await api.post('/security/auth/recuperar/verificar/', { email: email.trim(), codigo })
            setTemporal(data.temporary_password)
            setPaso(2)
        } catch (err) {
            const { fields, message } = parseApiError(err)
            setError(fields.codigo ?? err?.response?.data?.detail ?? message)
        } finally {
            setCargando(false)
        }
    }

    async function continuar() {
        setCargando(true)
        setError('')
        try {
            // La pantalla «Crea tu contraseña» usa la temporal sin que haya que escribirla.
            sessionStorage.setItem(CLAVE_TEMPORAL, temporal)
            await login(email.trim(), temporal) // PublicOnly redirige a /cambiar-clave
        } catch (err) {
            sessionStorage.removeItem(CLAVE_TEMPORAL)
            setError(parseApiError(err).message)
            setCargando(false)
        }
    }

    async function copiar() {
        try {
            await navigator.clipboard.writeText(temporal)
            setCopiado(true)
            setTimeout(() => setCopiado(false), 2000)
        } catch {
            // Sin permiso para el portapapeles: el usuario puede copiarla a mano.
        }
    }

    return (
        <div className="grid min-h-screen place-items-center bg-brand-50 px-4 py-10">
            <div className="w-full max-w-md">
                <Logo className="mb-6" />
                <Card>
                    <h1 className="text-2xl font-extrabold tracking-tight text-navy-800">Recuperar contraseña</h1>
                    <p className="mt-1 mb-6 text-ink-500">Te ayudamos a volver a ingresar a tu cuenta.</p>
                    <Pasos actual={paso} />
                    {error && <Alert className="mb-4">{error}</Alert>}

                    {paso === 0 && (
                        <form onSubmit={solicitar} noValidate>
                            <Field
                                label="Correo electrónico de tu cuenta"
                                type="email"
                                autoComplete="username"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                hint="Te enviaremos un código de 6 dígitos."
                            />
                            <Button type="submit" loading={cargando} disabled={!email} className="mt-6 w-full">
                                Enviar código
                            </Button>
                        </form>
                    )}

                    {paso === 1 && (
                        <form onSubmit={verificar} noValidate>
                            {aviso && <Alert tone="ok" className="mb-4">{aviso}</Alert>}
                            <Field
                                label="Código de verificación"
                                inputMode="numeric"
                                autoComplete="one-time-code"
                                maxLength={6}
                                value={codigo}
                                onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
                                className="[&_input]:text-center [&_input]:font-mono [&_input]:text-2xl [&_input]:tracking-[0.5em]"
                                hint={`Enviado a ${email.trim()}. Vence en 10 minutos.`}
                            />
                            <Button type="submit" loading={cargando} disabled={codigo.length !== 6} className="mt-6 w-full">
                                Verificar código
                            </Button>
                            <div className="mt-4 flex items-center justify-between text-sm">
                                <button type="button" onClick={() => { setPaso(0); setCodigo(''); setError('') }} className="font-bold text-brand-700 hover:underline">
                                    Cambiar correo
                                </button>
                                <button type="button" onClick={solicitar} disabled={espera > 0 || cargando} className="font-bold text-brand-700 hover:underline disabled:text-ink-300 disabled:no-underline">
                                    {espera > 0 ? `Reenviar en ${espera} s` : 'Reenviar código'}
                                </button>
                            </div>
                        </form>
                    )}

                    {paso === 2 && (
                        <div>
                            <Alert tone="ok" className="mb-4">Código verificado. También te enviamos esta contraseña por correo.</Alert>
                            <p className="mb-2 text-sm font-bold text-ink-700">Tu contraseña temporal</p>
                            <div className="flex items-center gap-2 rounded-xl border border-line bg-brand-50 p-3">
                                <code className="flex-1 text-center font-mono text-xl font-bold tracking-wider text-navy-800">{temporal}</code>
                                <Button variant="secondary" onClick={copiar} aria-label="Copiar contraseña temporal">
                                    {copiado ? <Check className="size-4" aria-hidden="true" /> : <Copy className="size-4" aria-hidden="true" />}
                                    {copiado ? 'Copiada' : 'Copiar'}
                                </Button>
                            </div>
                            <p className="mt-3 text-sm text-ink-500">
                                Solo se muestra una vez. En el siguiente paso crearás tu contraseña definitiva; se cerraron tus otras sesiones.
                            </p>
                            <Button onClick={continuar} loading={cargando} className="mt-6 w-full">
                                Crear mi contraseña nueva
                            </Button>
                        </div>
                    )}

                    <p className="mt-6 border-t border-line pt-4 text-sm">
                        <Link to="/login" className="inline-flex items-center gap-1 font-bold text-brand-700 hover:underline">
                            <ArrowLeft className="size-4" aria-hidden="true" />
                            Volver a iniciar sesión
                        </Link>
                    </p>
                </Card>
            </div>
        </div>
    )
}
