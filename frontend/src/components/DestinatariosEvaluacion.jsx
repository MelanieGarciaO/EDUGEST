import { Users } from 'lucide-react'

/**
 * Aviso bajo el check «Es una evaluación de refuerzo»: a quién irá o, si nadie completó su
 * plan, que no se puede publicar como evaluación.
 */
export default function DestinatariosEvaluacion({ consulta, error }) {
    if (consulta.isLoading) return <p className="text-sm text-ink-500">Buscando estudiantes con el plan completado…</p>
    if (consulta.isError) return null
    const estudiantes = consulta.data ?? []
    if (!estudiantes.length) {
        return (
            <p className="rounded-xl bg-warn-50 px-4 py-3 text-sm font-semibold text-warn-600">
                {error ||
                    'Ningún estudiante de este paralelo tiene un plan de refuerzo de esta asignatura completado y pendiente de evaluación. La evaluación de refuerzo es solo para quienes cumplieron el 100 % de su plan.'}
            </p>
        )
    }
    return (
        <div className="rounded-xl border border-ok-600/30 bg-ok-50 px-4 py-3 text-sm">
            <p className="flex items-center gap-1.5 font-bold text-ok-600">
                <Users className="size-4" aria-hidden="true" />
                Solo para {estudiantes.length === 1 ? 'este estudiante' : `estos ${estudiantes.length} estudiantes`} (completaron su plan al 100 %):
            </p>
            <ul className="mt-1 list-disc pl-6 text-ink-700">
                {estudiantes.map((e) => (
                    <li key={e.id}>{e.nombre}</li>
                ))}
            </ul>
            <p className="mt-1 text-xs text-ink-500">
                El resto del paralelo no la verá ni será calificado. Su nota cuenta en el promedio como recuperación.
            </p>
        </div>
    )
}
