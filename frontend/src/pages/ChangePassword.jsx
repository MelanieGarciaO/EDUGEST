import { useAuth } from '../auth/AuthContext'
import CambiarClaveForm from '../components/CambiarClaveForm'
import { Button, Card, Logo } from '../components/ui'

/**
 * Primer acceso con clave temporal. Solo se muestra mientras must_change_password es true
 * (lo controla RequireAccessStep). Al guardar, el guard lleva a términos o al inicio.
 */
export default function ChangePassword() {
    const { user, applySession, logout } = useAuth()

    return (
        <div className="grid min-h-screen place-items-center bg-brand-50 px-4 py-10">
            <div className="w-full max-w-md">
                <Logo className="mb-6" />
                <Card>
                    <h1 className="text-2xl font-extrabold tracking-tight text-navy-800">Crea tu contraseña</h1>
                    <p className="mt-1 mb-6 text-ink-500">
                        {`Hola, ${user.first_name}. Por seguridad, cambia la contraseña temporal antes de continuar.`}
                    </p>
                    <CambiarClaveForm
                        forced
                        onSuccess={applySession}
                        secondaryAction={
                            <Button variant="secondary" onClick={logout}>
                                Cerrar sesión
                            </Button>
                        }
                    />
                </Card>
            </div>
        </div>
    )
}
