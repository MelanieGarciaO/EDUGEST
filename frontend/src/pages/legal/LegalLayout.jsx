import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Printer } from 'lucide-react'

import { useAuth } from '../../auth/AuthContext'
import { Logo } from '../../components/ui'
import { fechaLegal, useLegalInfo } from '../../lib/legal'

/**
 * Página legal pública (se puede leer con o sin sesión).
 * `secciones`: [{ id, titulo, contenido }] — se genera el índice automáticamente.
 */
export default function LegalLayout({ titulo, resumen, secciones, otro }) {
    const navigate = useNavigate()
    const { status } = useAuth()
    const { version, vigenteDesde } = useLegalInfo()

    const volver = () => (window.history.length > 1 ? navigate(-1) : navigate(status === 'auth' ? '/' : '/login'))

    return (
        <div className="min-h-screen bg-brand-50">
            <header className="border-b border-line bg-white print:hidden">
                <div className="mx-auto flex max-w-4xl items-center justify-between gap-4 px-4 py-4 sm:px-8">
                    <Link to="/" aria-label="EduGest, ir al inicio">
                        <Logo />
                    </Link>
                    <button
                        type="button"
                        onClick={volver}
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl px-4 font-bold text-brand-700 hover:bg-brand-100"
                    >
                        <ArrowLeft className="size-4" aria-hidden="true" />
                        Volver
                    </button>
                </div>
            </header>

            <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
                <h1 className="text-3xl font-extrabold tracking-tight text-navy-800 sm:text-4xl">{titulo}</h1>
                {version && (
                    <p className="mt-2 text-sm font-semibold text-ink-500">
                        Versión {version}
                        {vigenteDesde && ` · vigente desde el ${fechaLegal(vigenteDesde)}`}
                    </p>
                )}
                <p className="mt-4 rounded-2xl bg-white p-5 text-[15px] leading-relaxed text-ink-700 shadow-sm">{resumen}</p>

                <nav aria-label="Contenido" className="mt-8 rounded-2xl border border-line bg-white p-5 print:hidden">
                    <p className="font-bold text-navy-800">Contenido</p>
                    <ol className="mt-3 grid gap-x-6 gap-y-1.5 text-[15px] sm:grid-cols-2">
                        {secciones.map((s, i) => (
                            <li key={s.id}>
                                <a href={`#${s.id}`} className="text-brand-700 hover:underline">
                                    {i + 1}. {s.titulo}
                                </a>
                            </li>
                        ))}
                    </ol>
                </nav>

                <div className="mt-8 space-y-8">
                    {secciones.map((s, i) => (
                        <section key={s.id} id={s.id} className="scroll-mt-6">
                            <h2 className="text-xl font-extrabold text-navy-800">
                                {i + 1}. {s.titulo}
                            </h2>
                            <div className="legal-texto mt-3 space-y-3 text-[15px] leading-relaxed text-ink-700">{s.contenido}</div>
                        </section>
                    ))}
                </div>

                <footer className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6 print:hidden">
                    <Link to={otro.to} className="font-bold text-brand-700 hover:underline">
                        {otro.label} →
                    </Link>
                    <button
                        type="button"
                        onClick={() => window.print()}
                        className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-line bg-white px-4 font-bold text-navy-800 hover:bg-brand-50"
                    >
                        <Printer className="size-4" aria-hidden="true" />
                        Imprimir o guardar en PDF
                    </button>
                </footer>
            </main>
        </div>
    )
}

/** Lista con viñetas para el contenido legal. */
export function Lista({ children }) {
    return <ul className="list-disc space-y-1.5 pl-6">{children}</ul>
}

/** Enlace de correo de contacto (o texto alternativo si no está configurado). */
export function Contacto({ correo, alternativa = 'la secretaría de la institución' }) {
    return correo ? (
        <a href={`mailto:${correo}`} className="font-bold text-brand-700 hover:underline">
            {correo}
        </a>
    ) : (
        <span>{alternativa}</span>
    )
}
