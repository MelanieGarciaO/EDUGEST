import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { CircleCheck, Clock, RefreshCw, ServerCrash, WifiOff, Wrench } from 'lucide-react'

import { checkHealth } from '../api/client'
import { systemStatus, useSystemStatus } from '../api/system'
import { Button, Logo } from './ui'

// Cada cuánto se vuelve a consultar /health/ mientras el sistema no está disponible.
const ESPERA = { offline: 5, down: 15, maintenance: 30 }

const PANTALLAS = {
    offline: {
        Icono: WifiOff,
        tono: 'bg-warn-50 text-warn-600',
        titulo: 'Sin conexión a internet',
        texto: 'Revisa tu wifi o tus datos móviles. EduGest se reconectará solo cuando vuelva la conexión.',
    },
    down: {
        Icono: ServerCrash,
        tono: 'bg-danger-50 text-danger-600',
        titulo: 'El sistema no está disponible',
        texto: 'No pudimos conectar con el servidor de EduGest. Puede ser una falla momentánea; lo intentaremos de nuevo automáticamente.',
    },
    maintenance: {
        Icono: Wrench,
        tono: 'bg-brand-100 text-brand-700',
        titulo: 'Estamos en mantenimiento',
        texto: 'Estamos realizando mejoras en EduGest. Volveremos a estar disponibles en breve.',
    },
}

/**
 * Pantalla que cubre la aplicación cuando el sistema se cae, se queda sin internet o entra
 * en mantenimiento. Se superpone (no desmonta la app), así que lo que el usuario estaba
 * escribiendo —por ejemplo, notas en «Calificar»— se conserva al volver el servicio.
 */
export default function SystemStatusOverlay() {
    const estado = useSystemStatus()
    const qc = useQueryClient()
    const [reconectado, setReconectado] = useState(false)

    // Al abrir la app se comprueba el servicio: así el mantenimiento se ve desde el login.
    // El navegador además avisa cuando pierde o recupera internet.
    useEffect(() => {
        if (navigator.onLine === false) systemStatus.set({ tipo: 'offline' })
        else checkHealth()
        const sinRed = () => systemStatus.set({ tipo: 'offline' })
        const conRed = () => {
            if (systemStatus.get().tipo !== 'ok') checkHealth()
        }
        window.addEventListener('offline', sinRed)
        window.addEventListener('online', conRed)
        return () => {
            window.removeEventListener('offline', sinRed)
            window.removeEventListener('online', conRed)
        }
    }, [])

    // Al volver el servicio: se recargan los datos que fallaron y se avisa brevemente.
    useEffect(() => {
        let anterior = systemStatus.get().tipo
        let temporizador
        const cancelar = systemStatus.subscribe(() => {
            const actual = systemStatus.get().tipo
            if (anterior !== 'ok' && actual === 'ok') {
                qc.invalidateQueries()
                setReconectado(true)
                clearTimeout(temporizador)
                temporizador = setTimeout(() => setReconectado(false), 4000)
            }
            anterior = actual
        })
        return () => {
            cancelar()
            clearTimeout(temporizador)
        }
    }, [qc])

    if (estado.tipo !== 'ok') return <PantallaEstado key={estado.tipo} estado={estado} />
    if (!reconectado) return null
    return (
        <div
            role="status"
            className="fixed bottom-5 left-1/2 z-[100] flex -translate-x-1/2 items-center gap-2 rounded-xl bg-ok-600 px-4 py-3 font-bold text-white shadow-lg"
        >
            <CircleCheck className="size-5" aria-hidden="true" />
            La conexión se restableció
        </div>
    )
}

/** Pantalla de un estado concreto. Se monta de nuevo (key) cada vez que cambia el estado. */
function PantallaEstado({ estado }) {
    const espera = ESPERA[estado.tipo] * 1000
    const [ahora, setAhora] = useState(() => Date.now())
    const [proximo, setProximo] = useState(() => Date.now() + espera)
    const [verificando, setVerificando] = useState(false)
    const boton = useRef(null)

    const verificar = useCallback(async () => {
        setVerificando(true)
        try {
            await checkHealth()
        } finally {
            setVerificando(false)
            setProximo(Date.now() + espera)
        }
    }, [espera])

    // Reintento automático con cuenta regresiva.
    useEffect(() => {
        const id = setInterval(() => setAhora(Date.now()), 1000)
        return () => clearInterval(id)
    }, [])
    const restante = Math.max(0, Math.ceil((proximo - ahora) / 1000))
    useEffect(() => {
        if (restante === 0 && !verificando) {
            const id = setTimeout(verificar, 0)
            return () => clearTimeout(id)
        }
        return undefined
    }, [restante, verificando, verificar])

    useEffect(() => {
        boton.current?.focus()
    }, [])

    const p = PANTALLAS[estado.tipo]
    const texto = estado.tipo === 'maintenance' && estado.mensaje ? estado.mensaje : p.texto

    return (
        <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="estado-sistema-titulo"
            aria-describedby="estado-sistema-texto"
            className="fixed inset-0 z-[100] grid place-items-center overflow-y-auto bg-brand-50/95 px-6 py-10 backdrop-blur-sm"
        >
            <div className="w-full max-w-md rounded-2xl border border-line bg-white p-8 text-center shadow-xl">
                <Logo className="mb-6" />
                <span className={`mx-auto grid size-16 place-items-center rounded-full ${p.tono}`}>
                    <p.Icono className="size-8" aria-hidden="true" />
                </span>
                <h1 id="estado-sistema-titulo" className="mt-5 text-2xl font-extrabold text-navy-800">
                    {p.titulo}
                </h1>
                <p id="estado-sistema-texto" className="mt-2 text-ink-500">{texto}</p>

                {estado.tipo === 'maintenance' && estado.hasta && (
                    <p className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand-50 px-4 py-2 text-sm font-bold text-navy-800">
                        <Clock className="size-4" aria-hidden="true" />
                        Regreso estimado: {estado.hasta}
                    </p>
                )}

                <Button ref={boton} className="mt-6 w-full" onClick={verificar} loading={verificando}>
                    <RefreshCw className="size-4" aria-hidden="true" />
                    {verificando ? 'Comprobando…' : 'Reintentar ahora'}
                </Button>
                <p className="mt-3 text-sm text-ink-500" aria-live="polite">
                    {verificando ? 'Comprobando el servicio…' : `Nuevo intento automático en ${restante} s`}
                </p>
                <p className="mt-5 text-xs text-ink-500">
                    No cierres esta pestaña: lo que estabas haciendo se conservará cuando vuelva el servicio.
                </p>
            </div>
        </div>
    )
}
