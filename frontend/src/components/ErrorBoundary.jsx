import { Component } from 'react'
import { House, RotateCcw, TriangleAlert } from 'lucide-react'

/**
 * Atrapa errores al dibujar una pantalla para que la aplicación no quede en blanco.
 *
 * - variant="page": dentro del menú lateral; el resto de la app sigue usable.
 *   Se reinicia sola al cambiar de ruta (resetKey).
 * - variant="full": último recurso, ocupa toda la pantalla.
 */
export default class ErrorBoundary extends Component {
    state = { error: null }

    static getDerivedStateFromError(error) {
        return { error }
    }

    componentDidCatch(error, info) {
        console.error('Error en la interfaz:', error, info?.componentStack)
    }

    componentDidUpdate(prev) {
        if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null })
    }

    reintentar = () => this.setState({ error: null })

    render() {
        const { error } = this.state
        if (!error) return this.props.children
        const full = this.props.variant === 'full'

        return (
            <div className={full ? 'grid min-h-screen place-items-center bg-brand-50 px-6' : 'py-16'} role="alert">
                <div className="mx-auto max-w-md text-center">
                    <span className="mx-auto grid size-16 place-items-center rounded-full bg-danger-50 text-danger-600">
                        <TriangleAlert className="size-8" aria-hidden="true" />
                    </span>
                    <h1 className="mt-5 text-2xl font-extrabold text-navy-800">Algo salió mal en esta pantalla</h1>
                    <p className="mt-2 text-ink-500">
                        Ocurrió un error inesperado al mostrar la información. Puedes intentarlo de nuevo o volver al inicio.
                    </p>
                    {import.meta.env.DEV && (
                        <pre className="mt-4 overflow-x-auto rounded-xl bg-white p-3 text-left text-xs text-danger-600">
                            {String(error?.message ?? error)}
                        </pre>
                    )}
                    <div className="mt-6 flex flex-wrap justify-center gap-3">
                        <button
                            type="button"
                            onClick={full ? () => window.location.reload() : this.reintentar}
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand-600 px-5 font-bold text-white hover:bg-brand-700"
                        >
                            <RotateCcw className="size-4" aria-hidden="true" />
                            {full ? 'Recargar' : 'Reintentar'}
                        </button>
                        <a
                            href="/"
                            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-line bg-white px-5 font-bold text-navy-800 hover:bg-brand-50"
                        >
                            <House className="size-4" aria-hidden="true" />
                            Ir al inicio
                        </a>
                    </div>
                </div>
            </div>
        )
    }
}
