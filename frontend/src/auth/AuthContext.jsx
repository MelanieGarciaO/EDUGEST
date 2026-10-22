import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { api, onSessionExpired, refreshAccess, tokenStore } from '../api/client'
import { estadoDesdeError, systemStatus, useSystemStatus } from '../api/system'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
    const queryClient = useQueryClient()
    const [user, setUser] = useState(null)
    // 'loading' mientras se intenta recuperar la sesión; luego 'auth' o 'anon'.
    const [status, setStatus] = useState('loading')
    const { tipo: sistema } = useSystemStatus()
    const [intento, setIntento] = useState(0)

    useEffect(() => {
        onSessionExpired(() => {
            setUser(null)
            setStatus('anon')
            queryClient.clear()
        })
    }, [queryClient])

    // Al abrir la aplicación, intenta retomar la sesión con el token de refresco guardado.
    useEffect(() => {
        let cancelado = false
        async function recuperar() {
            if (!tokenStore.getRefresh()) {
                setStatus('anon')
                return
            }
            try {
                await refreshAccess()
                const { data } = await api.get('/security/auth/me/')
                if (!cancelado) {
                    setUser(data)
                    setStatus('auth')
                }
            } catch (error) {
                if (cancelado) return
                const estatus = error?.response?.status
                if (estatus === 400 || estatus === 401 || estatus === 403) {
                    // El token de refresco ya no sirve: hay que iniciar sesión de nuevo.
                    tokenStore.clear()
                    setStatus('anon')
                    return
                }
                // El servidor no respondió: se conserva la sesión, se muestra la pantalla de
                // servicio no disponible y se reintenta cuando vuelva.
                systemStatus.set(estadoDesdeError(error) ?? { tipo: 'down' })
            }
        }
        recuperar()
        return () => {
            cancelado = true
        }
    }, [intento])

    // Cuando el sistema vuelve (pasa de caído a ok) y la sesión seguía pendiente, se reintenta.
    const sistemaAnterior = useRef(sistema)
    useEffect(() => {
        const volvio = sistemaAnterior.current !== 'ok' && sistema === 'ok'
        sistemaAnterior.current = sistema
        if (volvio && status === 'loading' && tokenStore.getRefresh()) setIntento((n) => n + 1)
    }, [sistema, status])

    const login = useCallback(async (email, password) => {
        const { data } = await api.post('/security/auth/login/', { email, password })
        tokenStore.set(data.access, data.refresh)
        setUser(data.user)
        setStatus('auth')
        return data.user
    }, [])

    const logout = useCallback(async () => {
        const refresh = tokenStore.getRefresh()
        try {
            if (refresh) await api.post('/security/auth/logout/', { refresh })
        } catch {
            // Aunque falle el aviso al servidor, la sesión local se cierra igual.
        }
        tokenStore.clear()
        setUser(null)
        setStatus('anon')
        queryClient.clear()
    }, [queryClient])

    /** Aplica la respuesta de "cambiar contraseña": tokens nuevos y usuario actualizado. */
    const applySession = useCallback((data) => {
        tokenStore.set(data.access, data.refresh)
        setUser(data.user)
        setStatus('auth')
    }, [])

    /** Reemplaza los datos del usuario (p. ej. tras aceptar los términos). */
    const updateUser = useCallback((data) => setUser(data), [])

    const value = useMemo(
        () => ({ user, status, login, logout, applySession, updateUser }),
        [user, status, login, logout, applySession, updateUser],
    )

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
    const context = useContext(AuthContext)
    if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider')
    return context
}
