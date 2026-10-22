import { useAuth } from '../auth/AuthContext'
import { Card, PageHeader, Spinner } from '../components/ui'
import { useCount } from '../lib/queries'

function Stat({ label, query }) {
    return (
        <Card as="div">
            <p className="text-sm font-bold text-ink-500">{label}</p>
            <p className="mt-1 text-3xl font-extrabold text-navy-800">
                {query.isPending ? <Spinner className="text-brand-600" /> : query.isError ? '—' : query.data}
            </p>
        </Card>
    )
}

export default function AdminHome() {
    const { user } = useAuth()
    const act = { is_active: 'true' }
    const docentes = useCount('docentes', '/security/users/', { role: 'DOCENTE', ...act })
    const representantes = useCount('representantes', '/security/users/', { role: 'REPRESENTANTE', ...act })
    const admins = useCount('admins', '/security/users/', { role: 'ADMINISTRADOR', ...act })
    const estudiantes = useCount('estudiantes', '/academic/estudiantes/', act)
    const paralelos = useCount('paralelos', '/academic/paralelos/', act)

    return (
        <>
            <PageHeader title={`¡Hola, ${user.first_name}!`} subtitle="Resumen de la institución." />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <Stat label="Docentes" query={docentes} />
                <Stat label="Representantes" query={representantes} />
                <Stat label="Administradores" query={admins} />
                <Stat label="Estudiantes" query={estudiantes} />
                <Stat label="Paralelos" query={paralelos} />
            </div>
        </>
    )
}
