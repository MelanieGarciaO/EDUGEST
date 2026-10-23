import { CalendarDays } from 'lucide-react'

import { diasRestantes, formatFecha, horaCorta, textoPlazo } from '../lib/dates'
import { formatNota } from '../lib/format'
import { MaterialesChips } from './Materiales'
import { NivelChip } from './Semaforo'
import { Chip, cx } from './ui'

/** Tarjeta de una actividad. `children` recibe las acciones (editar, cancelar…). */
export default function ActividadCard({ actividad: a, showDocente = false, children }) {
    const cancelada = a.vigencia === 'cancelada'
    const pendiente = a.vigencia === 'pendiente'
    const dias = diasRestantes(a.fecha_entrega)
    const hora = horaCorta(a.hora_entrega)
    // `notas` solo llega lleno para el representante; para el docente es null.
    const notas = Array.isArray(a.notas) ? a.notas : null
    const calificada = notas?.length > 0

    return (
        <article className={cx('rounded-2xl border border-line bg-white p-5', cancelada && 'opacity-75')}>
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                <div className="min-w-0 flex-1 basis-56">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-lg font-extrabold text-navy-800">{a.asignatura_nombre}</h3>
                        {a.tema && <Chip>{a.tema}</Chip>}
                        {a.es_evaluacion_refuerzo && <Chip tone="ok">Evaluación de refuerzo</Chip>}
                        {cancelada && <Chip tone="danger">Cancelada</Chip>}
                        {a.vigencia === 'finalizada' && !calificada && <Chip tone="warn">Finalizada</Chip>}
                        {calificada && <Chip tone="ok">Calificada</Chip>}
                    </div>
                    <p className="text-sm text-ink-500">
                        {a.paralelo_nombre}
                        {showDocente && ` · Docente: ${a.docente_nombre}`}
                    </p>
                </div>
                <div className="text-right">
                    <p
                        className={cx(
                            'flex items-center justify-end gap-1.5 font-bold',
                            cancelada ? 'text-ink-500 line-through' : pendiente ? 'text-danger-600' : 'text-ink-500',
                        )}
                    >
                        <CalendarDays className="size-4" aria-hidden="true" />
                        {formatFecha(a.fecha_entrega)}
                        {hora && <span> · {hora}</span>}
                    </p>
                    {pendiente && (
                        <p className={cx('text-sm font-semibold', dias <= 1 ? 'text-danger-600' : dias <= 3 ? 'text-warn-600' : 'text-ink-500')}>
                            {textoPlazo(a.fecha_entrega)}
                        </p>
                    )}
                </div>
            </div>

            <p className="mt-3 whitespace-pre-line text-ink-900">{a.descripcion}</p>

            {a.materiales?.length > 0 && (
                <div className="mt-3">
                    <p className="mb-1.5 text-sm font-bold text-ink-700">Materiales</p>
                    <MaterialesChips items={a.materiales} />
                </div>
            )}

            {notas && !cancelada && (calificada || a.vigencia === 'finalizada') && <NotasActividad notas={notas} />}

            {children && <div className="mt-4 flex flex-wrap justify-end gap-2 border-t border-line pt-3">{children}</div>}
        </article>
    )
}

/** Nota de cada estudiante del representante en la actividad. */
function NotasActividad({ notas }) {
    if (notas.length === 0) {
        return (
            <p className="mt-4 rounded-xl bg-brand-50 px-4 py-3 text-sm font-semibold text-ink-500">
                El docente aún no ha registrado la calificación.
            </p>
        )
    }
    return (
        <div className="mt-4 space-y-2">
            <p className="text-sm font-bold text-ink-700">Calificación</p>
            {notas.map((n) => (
                <div key={n.estudiante} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-brand-50 px-4 py-3">
                    <div className="min-w-0">
                        <p className="font-bold text-ink-900">{n.estudiante_nombre}</p>
                        <p className="text-sm text-ink-500">Tema: {n.tema_nombre}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <NivelChip nivel={n.nivel} />
                        <span className="text-2xl font-extrabold text-navy-800">
                            {formatNota(n.valor)}
                            <span className="text-sm font-bold text-ink-500"> / 10</span>
                        </span>
                    </div>
                </div>
            ))}
        </div>
    )
}
