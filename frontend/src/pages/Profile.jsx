import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import CambiarClaveForm from '../components/CambiarClaveForm'
import { Alert, Avatar, Button, Card, PageHeader } from '../components/ui'
import { ROLE_LABELS } from '../lib/roles'

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
                    <div className="mt-4">
                        <CambiarClaveForm
                            onSuccess={onClaveCambiada}
                            secondaryAction={
                                <Button variant="secondary" onClick={() => setCambiando(false)}>
                                    Cancelar
                                </Button>
                            }
                        />
                    </div>
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
