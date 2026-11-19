import { BookOpenText, Gamepad2, Hand, Headphones, Image, MonitorSmartphone, Video } from 'lucide-react'
import { cx } from '../lib/cx'
import { FORMATO_LABEL, FORMATOS } from '../lib/format'

const ICONOS = {
    TEXTO: BookOpenText,
    VISUAL: Image,
    AUDIO: Headphones,
    VIDEO: Video,
    MANIPULATIVO: Hand,
    JUEGO: Gamepad2,
    DIGITAL: MonitorSmartphone,
}

/** Chips de solo lectura con los formatos de un recurso o actividad. */
export function FormatosChips({ formatos, className }) {
    if (!formatos?.length) return null
    return (
        <span className={cx('inline-flex flex-wrap items-center gap-1.5', className)}>
            {formatos.map((f) => {
                const Icono = ICONOS[f]
                return (
                    <span
                        key={f}
                        className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-xs font-semibold text-ink-700"
                    >
                        {Icono && <Icono className="size-3.5 text-brand-700" aria-hidden="true" />}
                        {FORMATO_LABEL[f] ?? f}
                    </span>
                )
            })}
        </span>
    )
}

/** Selector múltiple (botones que se activan y desactivan) de formatos del recurso. */
export function FormatosSelector({ value, onChange, error, hint, max = 4 }) {
    const elegidos = value ?? []
    const alternar = (f) => {
        if (elegidos.includes(f)) onChange(elegidos.filter((x) => x !== f))
        else if (elegidos.length < max) onChange([...elegidos, f])
    }
    return (
        <fieldset>
            <legend className="mb-1.5 text-sm font-bold text-ink-900">Formato (DUA · representación)</legend>
            <div className="flex flex-wrap gap-2">
                {FORMATOS.map((f) => {
                    const activo = elegidos.includes(f.value)
                    const Icono = ICONOS[f.value]
                    return (
                        <button
                            key={f.value}
                            type="button"
                            aria-pressed={activo}
                            onClick={() => alternar(f.value)}
                            disabled={!activo && elegidos.length >= max}
                            className={cx(
                                'inline-flex min-h-10 items-center gap-1.5 rounded-full border px-3 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                                activo
                                    ? 'border-brand-600 bg-brand-600 text-white'
                                    : 'border-line bg-white text-ink-700 hover:border-brand-300 hover:bg-brand-50',
                            )}
                        >
                            <Icono className="size-4" aria-hidden="true" />
                            {f.label}
                        </button>
                    )
                })}
            </div>
            {error ? (
                <p className="mt-1.5 text-sm font-medium text-danger-600">{error}</p>
            ) : (
                hint && <p className="mt-1.5 text-sm text-ink-500">{hint}</p>
            )}
        </fieldset>
    )
}
