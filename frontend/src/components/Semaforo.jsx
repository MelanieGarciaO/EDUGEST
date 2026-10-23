import { ESCALA_LOEI, infoNivel } from '../lib/format'
import { cx } from './ui'

const PUNTO = { ok: 'bg-ok-600', brand: 'bg-brand-600', warn: 'bg-warn-600', danger: 'bg-danger-600' }
const FONDO = {
    ok: 'bg-ok-50 text-ok-600',
    brand: 'bg-brand-100 text-brand-700',
    warn: 'bg-warn-50 text-warn-600',
    danger: 'bg-danger-50 text-danger-600',
}

/** Chip del semáforo LOEI: punto de color + sigla oficial (DAR/AAR/PAAR/NAAR) + nombre corto. */
export function NivelChip({ nivel, corto = false }) {
    const info = infoNivel(nivel)
    if (!info) return null
    return (
        <span
            title={`${info.sigla}: ${info.nombre} (${info.rango})`}
            className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold', FONDO[info.tone])}
        >
            <span className={cx('size-2 rounded-full', PUNTO[info.tone])} aria-hidden="true" />
            <span>{info.sigla}</span>
            {corto ? null : <span className="font-semibold">{`· ${info.nombre.replace(' requeridos', '')}`}</span>}
        </span>
    )
}

/** Leyenda de la escala cualitativa (Reglamento General a la LOEI). */
export function LeyendaSemaforo({ className }) {
    return (
        <details className={cx('rounded-xl border border-line bg-white px-4 py-3 text-sm', className)}>
            <summary className="cursor-pointer font-bold text-ink-700">Escala cualitativa (LOEI)</summary>
            <ul className="mt-2 space-y-1.5">
                {ESCALA_LOEI.map((e) => (
                    <li key={e.nivel} className="flex flex-wrap items-center gap-2">
                        <span className={cx('size-2.5 rounded-full', PUNTO[e.tone])} aria-hidden="true" />
                        <span className="w-12 font-bold text-ink-900">{e.sigla}</span>
                        <span className="w-24 tabular-nums text-ink-500">{e.rango}</span>
                        <span className="text-ink-700">{e.nombre}</span>
                    </li>
                ))}
            </ul>
            <p className="mt-2 text-xs text-ink-500">PAAR: refuerzo preventivo · NAAR: plan de refuerzo obligatorio.</p>
        </details>
    )
}
