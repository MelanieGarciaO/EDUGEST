import { useState } from 'react'
import { BarChart3 } from 'lucide-react'

import { Alert, Card, Chip, EmptyState, PageHeader, SelectField, Spinner, cx } from '../components/ui'
import { LeyendaSemaforo, NivelChip } from '../components/Semaforo'
import { formatNota, reincidenciaLabel } from '../lib/format'
import { useDesempeno, useEstudiantes } from '../lib/queries'

const BARRA = { DOMINA: 'bg-ok-600', ALCANZA: 'bg-brand-600', PROXIMO: 'bg-warn-600', NO_ALCANZA: 'bg-danger-600' }

function Dificultad({ d }) {
    if (!d) return null
    if (d.estado === 'SUPERADA') return <Chip tone="ok">Dificultad superada</Chip>
    return (
        <>
            <Chip tone="danger">{`Dificultad ${d.nivel === 'ALTA' ? 'alta' : 'moderada'}`}</Chip>
            {d.reincidente ? <Chip tone="danger">{reincidenciaLabel(d.veces_detectada)}</Chip> : null}
        </>
    )
}

function Barra({ promedio, nivel }) {
    const pct = promedio == null ? 0 : Math.min(100, Number(promedio) * 10)
    return (
        <div className="h-2 w-full overflow-hidden rounded-full bg-brand-50" role="img" aria-label={`Promedio ${formatNota(promedio)} de 10`}>
            <div className={cx('h-full rounded-full', BARRA[nivel])} style={{ width: `${pct}%` }} />
        </div>
    )
}

function Tema({ t, nivelAnidado = 0 }) {
    return (
        <li>
            <div className={cx('py-3', nivelAnidado > 0 && 'pl-4 sm:pl-6')}>
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <p className={cx('text-ink-900', nivelAnidado === 0 ? 'font-bold' : 'font-semibold')}>{t.nombre}</p>
                        <Dificultad d={t.dificultad} />
                    </div>
                    <p className="flex items-center gap-2">
                        {t.promedio != null ? <NivelChip nivel={t.nivel} corto /> : null}
                        <span className="min-w-12 text-right text-lg font-extrabold text-navy-800">{t.promedio != null ? formatNota(t.promedio) : '—'}</span>
                    </p>
                </div>
                <div className="mt-2">
                    <Barra promedio={t.promedio} nivel={t.nivel} />
                </div>
                <p className="mt-1 text-xs text-ink-500">{t.calificaciones} {t.calificaciones === 1 ? 'nota' : 'notas'}</p>
            </div>
            {t.subtemas?.length > 0 && (
                <ul className="ml-1 divide-y divide-line border-l-2 border-brand-100">
                    {t.subtemas.map((s) => (
                        <Tema key={s.tema} t={s} nivelAnidado={nivelAnidado + 1} />
                    ))}
                </ul>
            )}
        </li>
    )
}

/** Desempeño académico de un estudiante. Lo usan el docente (sus asignaturas) y el representante. */
export default function Desempeno() {
    const estudiantes = useEstudiantes()
    const [elegido, setElegido] = useState('')
    const lista = estudiantes.data ?? []
    const estudianteId = elegido || (lista.length ? String(lista[0].id) : '')
    const desempeno = useDesempeno(estudianteId)

    return (
        <>
            <PageHeader title="Desempeño" subtitle="Promedio y nivel de aprendizaje por asignatura y tema." />
            <LeyendaSemaforo className="mb-5 max-w-3xl" />

            {estudiantes.isLoading && <Spinner />}
            {estudiantes.isError && <Alert>No se pudieron cargar los estudiantes. Intenta de nuevo.</Alert>}
            {estudiantes.isSuccess && lista.length === 0 && (
                <EmptyState icon={BarChart3} title="Aún no hay estudiantes para mostrar">
                    Cuando tengas estudiantes asociados, aquí verás su desempeño.
                </EmptyState>
            )}

            {lista.length > 0 && (
                <SelectField label="Estudiante" className="mb-6 max-w-sm" value={estudianteId} onChange={(e) => setElegido(e.target.value)}>
                    {lista.map((e) => (
                        <option key={e.id} value={e.id}>{e.full_name} · {e.paralelo_nombre}</option>
                    ))}
                </SelectField>
            )}

            {desempeno.isLoading && estudianteId && <Spinner />}
            {desempeno.isError && <Alert>No se pudo cargar el desempeño. Intenta de nuevo.</Alert>}
            {desempeno.data && desempeno.data.asignaturas.length === 0 && (
                <EmptyState icon={BarChart3} title={`${desempeno.data.estudiante.nombre} aún no tiene notas`}>
                    El desempeño aparecerá cuando el docente registre calificaciones.
                </EmptyState>
            )}
            <div className="max-w-3xl space-y-5">
                {desempeno.data?.asignaturas.map((a) => (
                    <Card key={a.asignatura} as="article">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <h2 className="text-lg font-extrabold text-navy-800">{a.nombre}</h2>
                                <p className="text-sm text-ink-500">{a.calificaciones} {a.calificaciones === 1 ? 'nota registrada' : 'notas registradas'}</p>
                            </div>
                            <div className="text-right">
                                <p className="text-3xl font-extrabold leading-none text-navy-800">{formatNota(a.promedio)}</p>
                                <div className="mt-1.5">
                                    <NivelChip nivel={a.nivel} />
                                </div>
                            </div>
                        </div>
                        <ul className="mt-3 divide-y divide-line border-t border-line">
                            {a.temas.map((t) => (
                                <Tema key={t.tema} t={t} />
                            ))}
                        </ul>
                    </Card>
                ))}
            </div>
        </>
    )
}
