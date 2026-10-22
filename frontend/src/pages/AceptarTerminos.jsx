import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { FileText, ShieldCheck } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Card, CheckboxField, Logo } from '../components/ui'
import { fechaLegal, useLegalInfo } from '../lib/legal'
import { ROLES, homeFor } from '../lib/roles'

/** Primer ingreso (o nueva versión): el usuario acepta los términos y la política de privacidad. */
export default function AceptarTerminos() {
    const { user, updateUser, logout } = useAuth()
    const navigate = useNavigate()
    const location = useLocation()
    const legal = useLegalInfo()
    const [acepto, setAcepto] = useState(false)
    const [autorizo, setAutorizo] = useState(false)
    const [enviando, setEnviando] = useState(false)
    const [error, setError] = useState('')

    const esRepresentante = user.role === ROLES.REPRESENTANTE
    const actualizacion = !!user.terminos_version // ya había aceptado una versión anterior
    const listo = acepto && (!esRepresentante || autorizo) && legal.isSuccess

    async function aceptar() {
        setEnviando(true)
        setError('')
        try {
            const { data } = await api.post('/security/auth/aceptar-terminos/', { version: legal.version, acepto: true })
            updateUser(data)
            navigate(location.state?.from && location.state.from !== '/' ? location.state.from : homeFor(data.role), { replace: true })
        } catch (err) {
            setError(parseApiError(err).message)
            legal.refetch()
        } finally {
            setEnviando(false)
        }
    }

    const enlace = (to, texto, Icono) => (
        <Link
            to={to}
            target="_blank"
            rel="noopener"
            className="flex min-h-12 items-center gap-3 rounded-xl border border-line px-4 font-bold text-navy-800 hover:bg-brand-50"
        >
            <Icono className="size-5 text-brand-700" aria-hidden="true" />
            {texto}
            <span className="ml-auto text-sm text-brand-700">Leer</span>
        </Link>
    )

    return (
        <div className="grid min-h-screen place-items-center bg-brand-50 px-4 py-10">
            <div className="w-full max-w-lg">
                <Logo className="mb-6" />
                <Card>
                    <h1 className="text-2xl font-extrabold tracking-tight text-navy-800">
                        {actualizacion ? 'Actualizamos nuestros términos' : 'Antes de empezar'}
                    </h1>
                    <p className="mt-1 text-ink-500">
                        {actualizacion
                            ? 'Publicamos una nueva versión de los términos de uso y de la política de privacidad. Revísalos para continuar.'
                            : `Hola, ${user.first_name}. Lee cómo ${legal.institucion} protege la información en EduGest.`}
                    </p>
                    {legal.version && (
                        <p className="mt-2 text-sm font-semibold text-ink-500">
                            Versión {legal.version}
                            {legal.vigenteDesde && ` · vigente desde el ${fechaLegal(legal.vigenteDesde)}`}
                        </p>
                    )}

                    <div className="mt-5 grid gap-2">
                        {enlace('/terminos', 'Términos de uso', FileText)}
                        {enlace('/privacidad', 'Política de privacidad', ShieldCheck)}
                    </div>

                    <div className="mt-5 space-y-3">
                        <CheckboxField
                            label="He leído y acepto los términos de uso y la política de privacidad"
                            checked={acepto}
                            onChange={(e) => setAcepto(e.target.checked)}
                        />
                        {esRepresentante && (
                            <CheckboxField
                                label="Autorizo el tratamiento de los datos académicos de mis representados"
                                hint="Como su representante legal, para las finalidades descritas en la política de privacidad: actividades, calificaciones, dificultades y planes de refuerzo."
                                checked={autorizo}
                                onChange={(e) => setAutorizo(e.target.checked)}
                            />
                        )}
                    </div>

                    {legal.isError && <Alert tone="error" className="mt-4">No se pudo cargar la versión vigente. Recarga la página.</Alert>}
                    {error && <Alert tone="error" className="mt-4">{error}</Alert>}

                    <Button className="mt-6 w-full" disabled={!listo} loading={enviando} onClick={aceptar}>
                        Aceptar y continuar
                    </Button>
                    <button
                        type="button"
                        onClick={logout}
                        className="mt-3 w-full text-center text-sm font-bold text-ink-500 hover:text-ink-700"
                    >
                        Ahora no, cerrar sesión
                    </button>
                </Card>
            </div>
        </div>
    )
}
