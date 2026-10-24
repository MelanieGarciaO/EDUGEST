import { CheckCircle2, Circle, Clock } from 'lucide-react'

import { ESTRATEGIA_LABEL, NIVEL_LABEL, NIVEL_TONE, PLAN_ESTADO_LABEL, PLAN_ESTADO_TONE, PLAN_NIVEL_LABEL, evaluacionPlan, formatNota } from '../lib/format'
import { Card, Chip, cx } from './ui'

const fecha = (iso) => new Date(iso).toLocaleDateString('es-EC', { day: 'numeric', month: 'long', year: 'numeric' })

/** Cabecera de un plan: estudiante, asignatura, estado y avance. */
export function PlanHeader({ plan, docente = false }) {
    const { avance } = plan
    const ev = evaluacionPlan(plan.evaluacion)
    return (
        <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-xl font-extrabold text-navy-800">{plan.estudiante_nombre}</h2>
                        <Chip tone={PLAN_ESTADO_TONE[plan.estado]}>{PLAN_ESTADO_LABEL[plan.estado]}</Chip>
                        <Chip tone={plan.nivel === 'ALTO' ? 'danger' : 'brand'}>{PLAN_NIVEL_LABEL[plan.nivel]}</Chip>
                        {ev && <Chip tone={ev.tone}>{ev.label}</Chip>}
                        {plan.revisado_en ? <Chip tone="ok">Revisado por la familia</Chip> : null}
                    </div>
                    <p className="text-ink-500">
                        {plan.asignatura_nombre} · {plan.paralelo_nombre} · Docente: {plan.docente_nombre}
                    </p>
                    <p className="mt-1 text-sm text-ink-500">
                        Creado el {fecha(plan.created_at)}
                        {plan.aprobado_en && ` · Aprobado el ${fecha(plan.aprobado_en)}`}
                        {plan.completado_en && ` · Completado el ${fecha(plan.completado_en)}`}
                        {plan.cancelado_en && ` · Cancelado el ${fecha(plan.cancelado_en)}`}
                    </p>
                    {plan.revisado_en ? (
                        <p className="mt-0.5 text-sm text-ok-600">
                            {`Revisado por ${plan.revisado_por_nombre ?? 'el representante'} el ${fecha(plan.revisado_en)}`}
                        </p>
                    ) : null}
                </div>
                <div className="min-w-44 flex-1 basis-44 sm:max-w-xs">
                    <p className="flex justify-between text-sm font-bold text-ink-700">
                        <span>Avance</span>
                        <span>{avance.porcentaje}%</span>
                    </p>
                    <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-brand-50" role="img" aria-label={`Avance del plan: ${avance.porcentaje}%`}>
                        <div className="h-full rounded-full bg-ok-600" style={{ width: `${avance.porcentaje}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-ink-500">
                        {avance.actividades_cumplidas} de {avance.actividades_total} actividades · {avance.temas_superados} de {avance.temas_total} temas superados
                    </p>
                </div>
            </div>
            {plan.evaluacion && <EvaluacionAviso evaluacion={plan.evaluacion} docente={docente} />}
        </Card>
    )
}

/** Qué sigue después de completar el plan. */
function EvaluacionAviso({ evaluacion: ev, docente }) {
    const textos = {
        PENDIENTE: docente
            ? 'El estudiante cumplió todas las actividades. Siguiente paso: publica una actividad marcada como «Evaluación de refuerzo» y califícala en el tema del plan.'
            : 'Todas las actividades están cumplidas. El docente evaluará el tema para comprobar el avance.',
        PARCIAL: 'Algunos temas ya tienen evaluación. Falta calificar los demás temas del plan.',
        SUPERADO: 'El estudiante superó los temas del plan. El ciclo de refuerzo quedó cerrado.',
        NO_SUPERADO: docente
            ? 'Algún tema no alcanzó 7,00 en la evaluación. Puedes generar un nuevo plan; se priorizarán actividades que el estudiante no ha hecho.'
            : 'Algún tema aún no alcanza el nivel esperado. El docente podrá asignar un nuevo plan de refuerzo.',
    }
    const clave = ev.estado === 'EVALUADO' ? ev.resultado : ev.estado
    const tono = clave === 'SUPERADO' ? 'bg-ok-50 text-ok-600' : clave === 'NO_SUPERADO' ? 'bg-danger-50 text-danger-600' : 'bg-warn-50 text-warn-600'
    return <p className={cx('mt-4 rounded-xl px-4 py-3 text-sm font-semibold', tono)}>{textos[clave]}</p>
}

/** Resultado de la evaluación de refuerzo de un tema. */
function TemaEvaluacion({ tema: t }) {
    if (t.superado == null) return null
    return (
        <div className={cx('mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3', t.superado ? 'bg-ok-50' : 'bg-danger-50')}>
            <div>
                <p className={cx('font-bold', t.superado ? 'text-ok-600' : 'text-danger-600')}>
                    {t.superado ? 'Evaluación superada' : 'Evaluación no superada'}
                </p>
                <p className="text-sm text-ink-700">
                    {t.evaluacion_fecha && `Evaluación del ${fecha(`${t.evaluacion_fecha}T12:00:00`)} · `}
                    Promedio: {t.promedio_inicial == null ? '—' : formatNota(t.promedio_inicial)} → <b>{formatNota(t.promedio_final)}</b>
                </p>
            </div>
            {t.nota_evaluacion != null && (
                <p className="text-2xl font-extrabold text-navy-800">
                    {formatNota(t.nota_evaluacion)}
                    <span className="text-sm font-bold text-ink-500"> / 10</span>
                </p>
            )}
        </div>
    )
}

/** Temas del plan con su objetivo y actividades. `actions(actividad, plan)` agrega botones por actividad y `temaActions(tema, plan)` botones del tema. */
export function PlanTemas({ plan, actions, temaActions }) {
    return (
        <div className="space-y-5">
            {plan.temas.map((t) => {
                const extra = temaActions?.(t, plan)
                return (
                    <Card as="article" key={t.id}>
                        <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                                <h3 className="text-lg font-extrabold text-navy-800">{t.tema_nombre}</h3>
                                {t.origen === 'MANUAL' ? (
                                    <Chip tone="brand">Refuerzo pedido por el docente</Chip>
                                ) : (
                                    <Chip tone={t.nivel_dificultad === 'ALTA' ? 'danger' : 'warn'}>
                                        {t.nivel_dificultad === 'ALTA' ? 'Dificultad alta' : 'Dificultad moderada'}
                                    </Chip>
                                )}
                                {t.dificultad_reincidente ? <Chip tone="danger">Reincidente</Chip> : null}
                                {(t.superado === true || (t.superado == null && t.dificultad_estado === 'SUPERADA')) && <Chip tone="ok">Tema superado</Chip>}
                            </div>
                            <p className="text-sm text-ink-500">
                                Promedio inicial:{' '}
                                <b className="text-ink-900">{t.promedio_inicial == null ? 'Sin notas' : formatNota(t.promedio_inicial)}</b>
                            </p>
                        </div>
                        {t.origen === 'MANUAL' && t.motivo && (
                            <p className="mt-2 text-sm text-ink-700">
                                <span className="font-bold">Motivo: </span>
                                {t.motivo}
                            </p>
                        )}
                        <p className="mt-2 text-ink-700">
                            <span className="font-bold">Objetivo: </span>
                            {t.objetivo}
                        </p>

                        {t.actividades.length === 0 ? (
                            <p className="mt-3 rounded-xl bg-warn-50 px-4 py-3 text-sm font-semibold text-warn-600">
                                {t.sin_recursos
                                    ? 'El banco de recursos no tenía actividades para este tema. Agrega una o carga recursos en el banco.'
                                    : 'Este tema no tiene actividades.'}
                            </p>
                        ) : (
                            <ol className="mt-3 divide-y divide-line border-t border-line">
                                {t.actividades.map((a) => {
                                    const cumplida = a.estado === 'CUMPLIDA'
                                    const acciones = actions?.(a, plan)
                                    return (
                                        <li key={a.id} className="py-3">
                                            <div className="flex items-start gap-3">
                                                {cumplida ? (
                                                    <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-ok-600" aria-label="Cumplida" />
                                                ) : (
                                                    <Circle className="mt-0.5 size-5 shrink-0 text-ink-300" aria-label="Pendiente" />
                                                )}
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <p className={cx('font-bold text-ink-900', cumplida && 'text-ink-500 line-through')}>{a.titulo}</p>
                                                        {a.nivel && <Chip tone={NIVEL_TONE[a.nivel]}>{NIVEL_LABEL[a.nivel]}</Chip>}
                                                        {a.estrategia && <Chip>{ESTRATEGIA_LABEL[a.estrategia]}</Chip>}
                                                        {a.origen === 'MANUAL' && <Chip>Agregada por el docente</Chip>}
                                                        {a.duracion_minutos && (
                                                            <span className="inline-flex items-center gap-1 text-xs font-semibold text-ink-500">
                                                                <Clock className="size-3.5" aria-hidden="true" />
                                                                {a.duracion_minutos} min
                                                            </span>
                                                        )}
                                                    </div>
                                                    <p className="mt-1 whitespace-pre-line text-sm text-ink-700">{a.instrucciones}</p>
                                                    {cumplida && a.cumplida_en && (
                                                        <p className="mt-1 text-xs text-ok-600">
                                                            Cumplida el {fecha(a.cumplida_en)}
                                                            {a.cumplida_por_nombre && ` por ${a.cumplida_por_nombre}`}
                                                        </p>
                                                    )}
                                                    {acciones && <div className="mt-2 flex flex-wrap gap-2">{acciones}</div>}
                                                </div>
                                            </div>
                                        </li>
                                    )
                                })}
                            </ol>
                        )}
                        <TemaEvaluacion tema={t} />
                        {extra && <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">{extra}</div>}
                    </Card>
                )
            })}
        </div>
    )
}
