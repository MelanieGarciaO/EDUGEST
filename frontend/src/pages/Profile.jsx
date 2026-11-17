import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, MailCheck } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import CambiarClaveForm from '../components/CambiarClaveForm'
import { Alert, Avatar, Button, Card, PageHeader } from '../components/ui'
import { ROLE_LABELS } from '../lib/roles'

const ESPERA = 60

/**
 * Cambio de contraseña desde el Perfil:
 * 1) el usuario pide una clave temporal -> le llega por correo (su contraseña actual no cambia);
 * 2) escribe esa clave y su contraseña nueva.
 */
function CambioDeClave({ email, onCambiada }) {
    const [paso, setPaso] = useState('inicio') // 'inicio' | 'enviada'
    const [aviso, setAviso] = useState('')
    const [error, setError] = useState('')
    const [enviando, setEnviando] = useState(false)
    const [espera, setEspera] = useState(0)

    useEffect(() => {
        if (!espera) return undefined
        const t = setTimeout(() => setEspera((s) => s - 1), 1000)
        return () => clearTimeout(t)
    }, [espera])

    async function pedirClave() {
        setError('')
        setEnviando(true)
        try {
            const { data } = await api.post('/security/auth/clave-temporal/')
            setAviso(data.detail)
            setPaso('enviada')
            setEspera(ESPERA)
        } catch (err) {
            setError(err?.response?.data?.detail ?? parseApiError(err).message)
        } finally {
            setEnviando(false)
        }
    }

    if (paso === 'inicio') {
        return (
            <div className="mt-3">
                <p className="text-sm text-ink-700">
                    {`Para cambiar tu contraseña te enviaremos una clave temporal a ${email}. Tu contraseña actual seguirá funcionando hasta que completes el cambio.`}
                </p>
                {error && <Alert className="mt-3">{error}</Alert>}
                <Button className="mt-4" onClick={pedirClave} loading={enviando}>
                    <MailCheck className="size-5" aria-hidden="true" />
                    Enviar clave temporal a mi correo
                </Button>
            </div>
        )
    }

    return (
        <div className="mt-3">
            <Alert tone="ok" className="mb-4">
                {aviso}
            </Alert>
            {error && <Alert className="mb-4">{error}</Alert>}
            <CambiarClaveForm
                onSuccess={onCambiada}
                etiquetaTemporal="Clave temporal"
                hintTemporal="Revisa tu bandeja de entrada y la carpeta de spam."
                secondaryAction={
                    <Button variant="secondary" onClick={pedirClave} loading={enviando} disabled={espera > 0}>
                        {espera > 0 ? `Reenviar en ${espera} s` : 'Reenviar clave'}
                    </Button>
                }
            />
        </div>
    )
}

export default function Profile() {
    const { user, applySession } = useAuth()
    const [cambiando, setCambiando] = useState(false)
    const [exito, setExito] = useState(false)

    function onClaveCambiada(data) {
        applySession(data) // tokens nuevos; el usuario sigue en Perfil
        setCambiando(false)
        setExito(true)
    }

    return (
        <>
            <PageHeader title="Perfil" />
            <Card className="max-w-xl">
                <div className="flex items-center gap-4">
                    <Avatar user={user} className="size-14 text-lg" />
                    <div>
                        <p className="text-lg font-extrabold text-navy-800">{`${user.first_name} ${user.last_name}`}</p>
                        <p className="text-ink-500">{ROLE_LABELS[user.role]}</p>
                    </div>
                </div>
                <dl className="mt-5 border-t border-line pt-4 text-sm">
                    <dt className="font-bold text-ink-700">Correo electrónico</dt>
                    <dd className="mt-0.5 text-ink-900">{user.email}</dd>
                    {user.terminos_aceptados_en ? (
                        <>
                            <dt className="mt-3 font-bold text-ink-700">Términos y privacidad</dt>
                            <dd className="mt-0.5 text-ink-900">
                                <span>
                                    {`Aceptaste la versión ${user.terminos_version} el ${new Date(user.terminos_aceptados_en).toLocaleDateString('es-EC', { day: 'numeric', month: 'long', year: 'numeric' })}. `}
                                </span>
                                <Link to="/terminos" className="font-bold text-brand-700 hover:underline">Términos</Link>
                                <span>{' · '}</span>
                                <Link to="/privacidad" className="font-bold text-brand-700 hover:underline">Privacidad</Link>
                            </dd>
                        </>
                    ) : null}
                </dl>
            </Card>

            <Card className="mt-4 max-w-xl">
                <h2 className="text-lg font-extrabold text-navy-800">Contraseña</h2>
                {exito ? (
                    <Alert tone="ok" className="mt-3">
                        Contraseña actualizada. Se cerraron tus sesiones en otros dispositivos.
                    </Alert>
                ) : null}
                {cambiando ? (
                    <>
                        <CambioDeClave email={user.email} onCambiada={onClaveCambiada} />
                        <button
                            type="button"
                            onClick={() => setCambiando(false)}
                            className="mt-4 text-sm font-bold text-ink-500 hover:text-ink-700 hover:underline"
                        >
                            Cancelar
                        </button>
                    </>
                ) : (
                    <Button
                        variant="secondary"
                        className="mt-4"
                        onClick={() => {
                            setExito(false)
                            setCambiando(true)
                        }}
                    >
                        <KeyRound className="size-5" aria-hidden="true" />
                        Cambiar contraseña
                    </Button>
                )}
            </Card>
        </>
    )
}
