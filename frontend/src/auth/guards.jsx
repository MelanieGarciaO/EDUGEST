import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { FullScreenSpinner } from '../components/ui'
import { homeFor } from '../lib/roles'
import { useAuth } from './AuthContext'

/**
 * Exige sesión iniciada. Si la clave es temporal, obliga a cambiarla primero; luego, si no
 * aceptó la versión vigente de los términos, lo lleva a aceptarlos.
 */
export function RequireAuth() {
    const { user, status } = useAuth()
    const location = useLocation()

    if (status === 'loading') return <FullScreenSpinner label="Cargando tu sesión" />
    if (status === 'anon') return <Navigate to="/login" replace state={{ from: location.pathname }} />
    if (user.must_change_password && location.pathname !== '/cambiar-clave') {
        return <Navigate to="/cambiar-clave" replace />
    }
    // Después de crear su contraseña, el usuario acepta los términos y la política de privacidad.
    if (!user.must_change_password && user.debe_aceptar_terminos && location.pathname !== '/aceptar-terminos') {
        return <Navigate to="/aceptar-terminos" replace state={{ from: location.pathname }} />
    }
    return <Outlet />
}

/** Permite el paso solo a los roles indicados; a los demás los lleva a su propio inicio. */
export function RequireRole({ roles }) {
    const { user } = useAuth()
    if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
    return <Outlet />
}

/** Para pantallas públicas (inicio de sesión): si ya hay sesión, redirige al inicio del rol. */
export function PublicOnly() {
    const { user, status } = useAuth()
    if (status === 'loading') return <FullScreenSpinner label="Cargando tu sesión" />
    if (status === 'auth') {
        const destino = user.must_change_password
            ? '/cambiar-clave'
            : user.debe_aceptar_terminos
              ? '/aceptar-terminos'
              : homeFor(user.role)
        return <Navigate to={destino} replace />
    }
    return <Outlet />
}

/** Redirige la raíz "/" al inicio que corresponde al rol. */
export function RootRedirect() {
    const { user } = useAuth()
    return <Navigate to={homeFor(user.role)} replace />
}
