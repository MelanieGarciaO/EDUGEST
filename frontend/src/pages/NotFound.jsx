import { Link } from 'react-router-dom'

import { Logo } from '../components/ui'

export default function NotFound() {
    return (
        <div className="grid min-h-screen place-items-center px-6 text-center">
            <div>
                <Logo className="mb-8" />
                <h1 className="text-3xl font-extrabold text-navy-800">No encontramos esta página</h1>
                <p className="mt-2 text-ink-500">La dirección no existe o ya no está disponible.</p>
                <Link
                    to="/"
                    className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-brand-600 px-5 font-bold text-white hover:bg-brand-700"
                >
                    Ir al inicio
                </Link>
            </div>
        </div>
    )
}
