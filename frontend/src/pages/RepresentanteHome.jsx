import { GraduationCap } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { Alert, Card, EmptyState, PageHeader, Spinner } from '../components/ui'
import { useAsignaciones, useEstudiantes } from '../lib/queries'

export default function RepresentanteHome() {
    const { user } = useAuth()
    const estudiantes = useEstudiantes()
    const asignaciones = useAsignaciones()

    const loading = estudiantes.isPending || asignaciones.isPending
    const failed = estudiantes.isError || asignaciones.isError

    return (
        <>
            <PageHeader title={`¡Hola, ${user.first_name}!`} subtitle="Aquí está el resumen de tus representados." />
            {loading ? (
                <Spinner className="text-brand-600" />
            ) : failed ? (
                <Alert>No pudimos cargar la información. Recarga la página para intentarlo de nuevo.</Alert>
            ) : estudiantes.data.length === 0 ? (
                <EmptyState icon={GraduationCap} title="Aún no hay estudiantes asociados a tu cuenta">
                    Comunícate con la administración de la institución para que los vinculen.
                </EmptyState>
            ) : (
                <ul className="grid gap-4 sm:grid-cols-2">
                    {estudiantes.data.map((e) => {
                        const materias = asignaciones.data.filter((a) => a.paralelo === e.paralelo)
                        return (
                            <li key={e.id}>
                                <Card as="article" className="h-full">
                                    <h2 className="text-lg font-extrabold text-navy-800">{e.full_name}</h2>
                                    <p className="text-sm text-ink-500">{e.paralelo_nombre}</p>
                                    {materias.length > 0 && (
                                        <ul className="mt-4 divide-y divide-line text-sm">
                                            {materias.map((m) => (
                                                <li key={m.id} className="flex justify-between gap-3 py-2">
                                                    <span className="font-bold text-ink-900">{m.asignatura_nombre}</span>
                                                    <span className="text-ink-500">{m.docente_nombre}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    )}
                                </Card>
                            </li>
                        )
                    })}
                </ul>
            )}
        </>
    )
}
