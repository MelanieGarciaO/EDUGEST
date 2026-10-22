import { Link } from 'react-router-dom'
import { KeyRound } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { Avatar, Card, PageHeader } from '../components/ui'
import { ROLE_LABELS } from '../lib/roles'

export default function Profile() {
    const { user } = useAuth()
    return (
        <>
            <PageHeader title="Perfil" />
            <Card className="max-w-xl">
                <div className="flex items-center gap-4">
                    <Avatar user={user} className="size-14 text-lg" />
                    <div>
                        <p className="text-lg font-extrabold text-navy-800">
                            {user.first_name} {user.last_name}
                        </p>
                        <p className="text-ink-500">{ROLE_LABELS[user.role]}</p>
                    </div>
                </div>
                <dl className="mt-5 border-t border-line pt-4 text-sm">
                    <dt className="font-bold text-ink-700">Correo electrónico</dt>
                    <dd className="mt-0.5 text-ink-900">{user.email}</dd>
                    {user.terminos_aceptados_en && (
                        <>
                            <dt className="mt-3 font-bold text-ink-700">Términos y privacidad</dt>
                            <dd className="mt-0.5 text-ink-900">
                                Aceptaste la versión {user.terminos_version} el{' '}
                                {new Date(user.terminos_aceptados_en).toLocaleDateString('es-EC', { day: 'numeric', month: 'long', year: 'numeric' })}.{' '}
                                <Link to="/terminos" className="font-bold text-brand-700 hover:underline">Términos</Link>
                                {' · '}
                                <Link to="/privacidad" className="font-bold text-brand-700 hover:underline">Privacidad</Link>
                            </dd>
                        </>
                    )}
                </dl>
                <Link
                    to="/cambiar-clave"
                    className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border border-line px-4 font-bold text-navy-800 hover:bg-brand-50"
                >
                    <KeyRound className="size-5" aria-hidden="true" />
                    Cambiar contraseña
                </Link>
            </Card>
        </>
    )
}
