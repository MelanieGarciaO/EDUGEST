import { Navigate, Outlet } from 'react-router-dom'

import { FullScreenSpinner } from '../components/ui'
import { destinoTrasAcceso, homeFor } from '../lib/roles'
import { useAuth } from './AuthContext'

/**
 * Exige sesión iniciada y que el acceso esté completo (clave definitiva y términos aceptados).
 * Si falta un paso, lleva a ese paso. Las redirecciones salen siempre del estado del usuario,
 * nunca de la URL anterior, así no se puede "volver" a una pantalla de acceso ya superada.
 */
export function RequireAuth() {
    const { user, status } = useAuth()
    if (status === 'loading') return <FullScreenSpinner label="Cargando tu sesión" />
    if (status === 'anon') return <Navigate to="/login" replace />
    if (user.must_change_password || user.debe_aceptar_terminos) {
        return <Navigate to={destinoTrasAcceso(user)} replace />
    }
    return <Outlet />
}

/**
 * Pantallas del proceso de acceso (/cambiar-clave y /aceptar-terminos).
 * Solo se muestran si ese es el paso pendiente; si no, llevan al destino correcto.
 */
export function RequireAccessStep({ path }) {
    const { user, status } = useAuth()
    if (status === 'loading') return <FullScreenSpinner label="Cargando tu sesión" />
    if (status === 'anon') return <Navigate to="/login" replace />
    const destino = destinoTrasAcceso(user)
    if (destino !== path) return <Navigate to={destino} replace />
    return <Outlet />
}

/** Permite el paso solo a los roles indicados; a los demás los lleva a su propio inicio. */
export function RequireRole({ roles }) {
    const { user } = useAuth()
    if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
    return <Outlet />
}

/** Para pantallas públicas (inicio de sesión): si ya hay sesión, lleva al siguiente paso o al inicio. */
export function PublicOnly() {
    const { user, status } = useAuth()
    if (status === 'loading') return <FullScreenSpinner label="Cargando tu sesión" />
    if (status === 'auth') return <Navigate to={destinoTrasAcceso(user)} replace />
    return <Outlet />
}

/** Redirige la raíz "/" al inicio que corresponde al rol. */
export function RootRedirect() {
    const { user } = useAuth()
    return <Navigate to={homeFor(user.role)} replace />
}
