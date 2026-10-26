import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BookOpen, ClipboardCheck, Repeat, School, Users } from 'lucide-react'

import { api } from '../api/client'
import { formatNota } from '../lib/format'
import { NivelChip } from './Semaforo'
import { Alert, Card, Spinner, cx } from './ui'

const pct = (n) => `${String(n).replace('.', ',')} %`

function Kpi({ icon: Icon, label, value, hint, tone = 'brand' }) {
    const color = { brand: 'text-brand-600 bg-brand-50', warn: 'text-warn-600 bg-warn-50', danger: 'text-danger-600 bg-danger-50', ok: 'text-ok-600 bg-ok-50' }[tone]
    return (
        <Card as="div" className="flex items-start gap-3">
            <span className={cx('grid size-10 shrink-0 place-items-center rounded-xl', color)}>
                <Icon className="size-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
                <p className="text-sm font-bold text-ink-500">{label}</p>
                <p className="text-2xl font-extrabold text-navy-800">{value}</p>
                {hint ? <p className="text-xs text-ink-500">{hint}</p> : null}
            </div>
        </Card>
    )
}

/** Barra horizontal (0–100 %). */
function Barra({ valor, tone = 'brand', label }) {
    const color = { brand: 'bg-brand-600', warn: 'bg-warn-600', danger: 'bg-danger-600', ok: 'bg-ok-600' }[tone]
    return (
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-brand-50" role="img" aria-label={label}>
            <div className={cx('h-full rounded-full', color)} style={{ width: `${Math.min(100, Math.max(2, valor))}%` }} />
        </div>
    )
}

function Panel({ icon: Icon, title, subtitle, vacio, children }) {
    return (
        <Card as="section">
            <h2 className="flex items-center gap-2 text-lg font-extrabold text-navy-800">
                <Icon className="size-5 text-brand-600" aria-hidden="true" />
                {title}
            </h2>
            <p className="mb-4 text-sm text-ink-500">{subtitle}</p>
            {vacio ? <p className="text-sm text-ink-500">{vacio}</p> : <ul className="space-y-3">{children}</ul>}
        </Card>
    )
}

/** Tablero de alerta temprana institucional (mejora 10). */
export default function AlertaTemprana() {
    const q = useQuery({
        queryKey: ['alerta-temprana'],
        queryFn: async () => (await api.get('/reinforcement/alerta-temprana/')).data,
    })
    if (q.isPending) return <Spinner />
    if (q.isError) return <Alert>No se pudo cargar el tablero de alerta temprana.</Alert>

    const { resumen: r, asignaturas_en_refuerzo: asig, paralelos_menor_rendimiento: par, temas_mayor_dificultad: temas } = q.data
    const maxAsig = Math.max(1, ...asig.map((a) => a.estudiantes))

    return (
        <div className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Kpi icon={Users} tone={r.porcentaje_con_dificultad >= 30 ? 'danger' : 'warn'} label="Estudiantes con dificultad" value={r.con_dificultad} hint={`${pct(r.porcentaje_con_dificultad)} de ${r.estudiantes}`} />
                <Kpi icon={Repeat} tone="danger" label="Reincidentes" value={r.reincidentes} hint="Volvieron a tener dificultad" />
                <Kpi icon={AlertTriangle} tone="brand" label="Planes en curso" value={r.planes_en_curso} />
                <Kpi icon={ClipboardCheck} tone="ok" label="Planes revisados por la familia" value={pct(r.planes_revisados_por_familia)} />
            </div>

            <div className="grid gap-5 lg:grid-cols-3">
                <Panel icon={BookOpen} title="Asignaturas en refuerzo" subtitle="Estudiantes con dificultad vigente o plan en curso." vacio={asig.length ? null : 'Ninguna asignatura tiene estudiantes en refuerzo.'}>
                    {asig.map((a) => (
                        <li key={a.asignatura}>
                            <div className="mb-1 flex justify-between gap-2 text-sm">
                                <span className="font-bold text-ink-900">{a.nombre}</span>
                                <span className="tabular-nums text-ink-700">{a.estudiantes}</span>
                            </div>
                            <Barra valor={(a.estudiantes * 100) / maxAsig} tone="warn" label={`${a.estudiantes} estudiantes`} />
                        </li>
                    ))}
                </Panel>

                <Panel icon={School} title="Paralelos con menor rendimiento" subtitle="Promedio de todas las notas del paralelo." vacio={par.length ? null : 'Aún no hay notas registradas.'}>
                    {par.map((p) => (
                        <li key={p.paralelo}>
                            <div className="mb-1 flex flex-wrap items-center justify-between gap-2 text-sm">
                                <span className="font-bold text-ink-900">{p.nombre}</span>
                                <span className="flex items-center gap-2">
                                    <span className="font-bold tabular-nums text-navy-800">{formatNota(p.promedio)}</span>
                                    <NivelChip nivel={p.nivel} corto />
                                </span>
                            </div>
                            <Barra valor={Number(p.promedio) * 10} tone={{ DOMINA: 'ok', ALCANZA: 'brand', PROXIMO: 'warn', NO_ALCANZA: 'danger' }[p.nivel]} label={`Promedio ${formatNota(p.promedio)}`} />
                        </li>
                    ))}
                </Panel>

                <Panel icon={AlertTriangle} title="Temas con más dificultad" subtitle="% de estudiantes calificados con dificultad." vacio={temas.length ? null : 'No hay dificultades vigentes.'}>
                    {temas.map((t) => (
                        <li key={t.tema}>
                            <div className="mb-1 flex justify-between gap-2 text-sm">
                                <span className="min-w-0">
                                    <span className="block font-bold text-ink-900">{t.nombre}</span>
                                    <span className="block text-xs text-ink-500">{`${t.asignatura} · ${t.grado}`}</span>
                                </span>
                                <span className="shrink-0 text-right tabular-nums">
                                    <span className="block font-bold text-danger-600">{pct(t.indice)}</span>
                                    <span className="block text-xs text-ink-500">{`${t.con_dificultad} de ${t.calificados}${t.reincidentes ? ` · ${t.reincidentes} reinc.` : ''}`}</span>
                                </span>
                            </div>
                            <Barra valor={t.indice} tone="danger" label={`${pct(t.indice)} con dificultad`} />
                        </li>
                    ))}
                </Panel>
            </div>
        </div>
    )
}
