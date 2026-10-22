import { School } from 'lucide-react'

import { useAuth } from '../auth/AuthContext'
import { Alert, Card, Chip, EmptyState, PageHeader, Spinner } from '../components/ui'
import { useAsignaciones, useParalelos } from '../lib/queries'

export default function DocenteHome() {
    const { user } = useAuth()
    const paralelos = useParalelos()
    const asignaciones = useAsignaciones()

    const loading = paralelos.isPending || asignaciones.isPending
    const failed = paralelos.isError || asignaciones.isError

    const grupos = (paralelos.data ?? []).map((p) => ({
        ...p,
        asignaturas: (asignaciones.data ?? []).filter((a) => a.paralelo === p.id),
    }))

    return (
        <>
            <PageHeader title={`¡Hola, ${user.first_name}!`} subtitle="Estos son los grupos que tienes a cargo este periodo." />
            <h2 className="mb-3 text-lg font-extrabold text-navy-800">Mis grupos</h2>
            {loading ? (
                <Spinner className="text-brand-600" />
            ) : failed ? (
                <Alert>No pudimos cargar tus grupos. Recarga la página para intentarlo de nuevo.</Alert>
            ) : grupos.length === 0 ? (
                <EmptyState icon={School} title="Aún no tienes grupos asignados">
                    La administración debe asignarte un paralelo y una asignatura para que aparezcan aquí.
                </EmptyState>
            ) : (
                <ul className="grid gap-4 sm:grid-cols-2">
                    {grupos.map((g) => (
                        <li key={g.id}>
                            <Card as="article" className="h-full">
                                <h3 className="text-lg font-extrabold text-navy-800">{g.nombre_completo}</h3>
                                <p className="text-sm text-ink-500">
                                    {g.estudiantes_count} {g.estudiantes_count === 1 ? 'estudiante' : 'estudiantes'}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {g.asignaturas.map((a) => (
                                        <Chip key={a.id}>{a.asignatura_nombre}</Chip>
                                    ))}
                                </div>
                            </Card>
                        </li>
                    ))}
                </ul>
            )}
        </>
    )
}
