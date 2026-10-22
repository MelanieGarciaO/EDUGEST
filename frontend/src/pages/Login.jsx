import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BookOpenCheck, Users, TrendingUp } from 'lucide-react'

import { parseApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert, Button, Field, Logo, PasswordField } from '../components/ui'

const VALORES = [
    { icon: BookOpenCheck, titulo: 'Docentes que organizan', texto: 'Actividades, notas y refuerzos en un solo lugar.' },
    { icon: Users, titulo: 'Familias que se informan', texto: 'Cada representante ve lo que necesita su hijo, a tiempo.' },
    { icon: TrendingUp, titulo: 'Estudiantes que avanzan', texto: 'Planes de refuerzo según las dificultades detectadas.' },
]

export default function Login() {
    const { login } = useAuth()
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    async function onSubmit(e) {
        e.preventDefault()
        setError('')
        setLoading(true)
        try {
            // Al guardar la sesión, PublicOnly redirige solo: clave temporal -> crear clave;
            // términos pendientes -> aceptarlos; en otro caso -> inicio del rol.
            await login(email.trim(), password)
        } catch (err) {
            const { status, message } = parseApiError(err)
            setError(status === 401 || status === 400 ? 'Correo o contraseña incorrectos.' : message)
            setLoading(false)
        }
    }

    return (
        <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
            <section className="flex flex-col justify-between gap-10 bg-navy-800 px-6 py-8 text-white sm:px-12 sm:py-12">
                <Logo light />
                <div className="max-w-lg">
                    <h1 className="text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">
                        Conectando docentes y familias por una educación más organizada
                    </h1>
                    <ul className="mt-8 hidden space-y-5 sm:block">
                        {VALORES.map(({ icon: Icon, titulo, texto }) => (
                            <li key={titulo} className="flex gap-4">
                                <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-navy-700">
                                    <Icon className="size-5" aria-hidden="true" />
                                </span>
                                <div>
                                    <p className="font-bold">{titulo}</p>
                                    <p className="text-sm text-brand-200">{texto}</p>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>
                <p className="hidden text-sm text-brand-200 sm:block">Educación General Básica · Guayaquil</p>
            </section>

            <main className="grid place-items-center bg-white px-6 py-10">
                <form onSubmit={onSubmit} className="w-full max-w-sm" noValidate>
                    <h2 className="text-2xl font-extrabold tracking-tight text-navy-800">Iniciar sesión</h2>
                    <p className="mt-1 text-ink-500">Ingresa con la cuenta que te entregó la institución.</p>

                    {error && <Alert className="mt-5">{error}</Alert>}

                    <Field
                        className="mt-6"
                        label="Correo electrónico"
                        type="email"
                        autoComplete="username"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                    />
                    <PasswordField
                        className="mt-4"
                        label="Contraseña"
                        autoComplete="current-password"
                        required
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                    />
                    <Button type="submit" loading={loading} disabled={!email || !password} className="mt-6 w-full">
                        Ingresar
                    </Button>
                    <p className="mt-5 text-sm text-ink-500">
                        ¿Olvidaste tu contraseña? Solicita una nueva a la administración de tu institución.
                    </p>
                    <p className="mt-6 border-t border-line pt-4 text-sm text-ink-500">
                        Al ingresar aceptas los{' '}
                        <Link to="/terminos" className="font-bold text-brand-700 hover:underline">términos de uso</Link> y la{' '}
                        <Link to="/privacidad" className="font-bold text-brand-700 hover:underline">política de privacidad</Link>.
                    </p>
                </form>
            </main>
        </div>
    )
}
