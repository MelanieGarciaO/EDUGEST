import { useMemo } from 'react'
import { cx } from '../lib/cx'
import { estructurarDescripcion } from '../lib/descripcion'

/**
 * Descripción de una actividad con estructura: títulos de sección en negrita, «Parte N»
 * como subtítulo y listas numeradas o con letras con sangría. Se usa en la lista de
 * actividades y en la pantalla de calificar.
 */
export default function DescripcionActividad({ texto, className }) {
    const lineas = useMemo(() => estructurarDescripcion(texto), [texto])
    if (!lineas.length) return null

    return (
        <div className={cx('space-y-1 leading-relaxed break-words', className)}>
            {lineas.map((l, i) => {
                switch (l.tipo) {
                    case 'espacio':
                        return <div key={i} className="h-1" aria-hidden="true" />
                    case 'encabezado':
                        return <p key={i} className="font-bold tracking-wide text-navy-900">{l.texto}</p>
                    case 'parte':
                        return (
                            <p key={i} className={cx(i > 0 && 'pt-2')}>
                                <span className="font-semibold text-navy-800">{l.etiqueta}.</span>
                                {l.texto && <span> {l.texto}</span>}
                            </p>
                        )
                    case 'titulo':
                        return (
                            <p key={i} className={cx(i > 0 && 'pt-2')}>
                                <span className="font-semibold text-navy-800">{l.etiqueta}</span>
                                {l.texto && <span className="block">{l.texto}</span>}
                            </p>
                        )
                    case 'numero':
                        return (
                            <p key={i} className="flex gap-2 pl-4">
                                <span className="min-w-[1.5rem] shrink-0 font-medium text-ink-500">{l.etiqueta}</span>
                                <span className="min-w-0">{l.texto}</span>
                            </p>
                        )
                    case 'letra':
                        return (
                            <p key={i} className="flex gap-2 pl-10">
                                <span className="min-w-[1.25rem] shrink-0 font-medium text-ink-500">{l.etiqueta}</span>
                                <span className="min-w-0">{l.texto}</span>
                            </p>
                        )
                    default:
                        return <p key={i}>{l.texto}</p>
                }
            })}
        </div>
    )
}
