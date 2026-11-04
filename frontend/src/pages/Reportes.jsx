import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { FileSpreadsheet, FileText } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { Alert, Button, Card, Field, PageHeader, SelectField, Spinner } from '../components/ui'
import { useAuth } from '../auth/AuthContext'
import { ROLES } from '../lib/roles'

const ETIQUETAS = {
    paralelo: 'Paralelo',
    asignatura: 'Asignatura',
    estudiante: 'Estudiante',
    estado_dificultad: 'Estado',
    estado_plan: 'Estado del plan',
}

const SUBTITULOS = {
    [ROLES.ADMINISTRADOR]: 'Descarga reportes de toda la institución en PDF o Excel.',
    [ROLES.DOCENTE]: 'Descarga reportes de tus paralelos y asignaturas en PDF o Excel.',
    [ROLES.REPRESENTANTE]: 'Descarga en PDF el avance de tu representado.',
}

/** Convierte el error de una descarga (la respuesta llega como Blob) a un mensaje legible. */
async function errorDeDescarga(error) {
    const data = error?.response?.data
    if (data instanceof Blob) {
        try {
            error.response.data = JSON.parse(await data.text())
        } catch {
            error.response.data = {}
        }
    }
    const parsed = parseApiError(error)
    const campo = Object.values(parsed.fields)[0]
    if (error?.response?.status === 404) return 'No se encontró la información solicitada.'
    return campo ?? parsed.message
}

function nombreDesdeCabecera(cabecera, alternativo) {
    const match = /filename="?([^";]+)"?/i.exec(cabecera ?? '')
    return match?.[1] ?? alternativo
}

async function descargar(clave, formato, filtros) {
    const params = { formato }
    for (const [k, v] of Object.entries(filtros)) if (v) params[k] = v
    const res = await api.get(`/reports/${clave}/`, { params, responseType: 'blob', timeout: 120_000 })
    const url = URL.createObjectURL(res.data)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = nombreDesdeCabecera(res.headers['content-disposition'], `edugest_${clave}.${formato}`)
    document.body.appendChild(enlace)
    enlace.click()
    enlace.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function TarjetaReporte({ reporte, opciones }) {
    const unico = opciones.estudiante?.length === 1 ? String(opciones.estudiante[0].id) : ''
    const [filtros, setFiltros] = useState(() => (reporte.filtros.includes('estudiante') ? { estudiante: unico } : {}))
    const [cargando, setCargando] = useState('')
    const [error, setError] = useState('')

    const set = (k) => (e) => setFiltros((f) => ({ ...f, [k]: e.target.value }))
    const faltan = reporte.requeridos.filter((k) => !filtros[k])

    async function bajar(formato) {
        setError('')
        setCargando(formato)
        try {
            await descargar(reporte.clave, formato, filtros)
        } catch (e) {
            setError(await errorDeDescarga(e))
        } finally {
            setCargando('')
        }
    }

    return (
        <Card className="flex flex-col gap-4">
            <div>
                <h2 className="text-lg font-extrabold text-navy-800">{reporte.titulo}</h2>
                <p className="text-sm text-ink-500">{reporte.descripcion}</p>
            </div>

            {reporte.filtros.length > 0 && (
                <div className="grid gap-3 sm:grid-cols-2">
                    {reporte.filtros.map((k) => {
                        if (k === 'desde' || k === 'hasta') {
                            return (
                                <Field
                                    key={k}
                                    type="date"
                                    label={k === 'desde' ? 'Entregas desde' : 'Entregas hasta'}
                                    value={filtros[k] ?? ''}
                                    onChange={set(k)}
                                />
                            )
                        }
                        const lista = opciones[k] ?? []
                        const requerido = reporte.requeridos.includes(k)
                        return (
                            <SelectField key={k} label={ETIQUETAS[k]} value={filtros[k] ?? ''} onChange={set(k)} className={k === 'estudiante' ? 'sm:col-span-2' : undefined}>
                                <option value="">{requerido ? 'Selecciona…' : 'Todos'}</option>
                                {lista.map((o) => (
                                    <option key={o.id} value={o.id}>
                                        {o.paralelo ? `${o.nombre} · ${o.paralelo}` : o.nombre}
                                    </option>
                                ))}
                            </SelectField>
                        )
                    })}
                </div>
            )}

            {error && <Alert>{error}</Alert>}

            <div className="mt-auto flex flex-wrap gap-2 border-t border-line pt-4">
                {reporte.formatos.includes('pdf') && (
                    <Button onClick={() => bajar('pdf')} loading={cargando === 'pdf'} disabled={!!cargando || faltan.length > 0}>
                        <FileText className="size-4" aria-hidden="true" />
                        Descargar PDF
                    </Button>
                )}
                {reporte.formatos.includes('xlsx') && (
                    <Button variant="secondary" onClick={() => bajar('xlsx')} loading={cargando === 'xlsx'} disabled={!!cargando || faltan.length > 0}>
                        <FileSpreadsheet className="size-4" aria-hidden="true" />
                        Descargar Excel
                    </Button>
                )}
            </div>
        </Card>
    )
}

export default function Reportes() {
    const { user } = useAuth()
    const catalogo = useQuery({
        queryKey: ['reportes', 'catalogo'],
        queryFn: async () => (await api.get('/reports/')).data,
    })

    return (
        <>
            <PageHeader title="Reportes" subtitle={SUBTITULOS[user?.role]} />
            {catalogo.isPending && <Spinner className="text-brand-600" />}
            {catalogo.isError && <Alert>{parseApiError(catalogo.error).message}</Alert>}
            {catalogo.isSuccess && user?.role === ROLES.REPRESENTANTE && !catalogo.data.opciones.estudiante?.length && (
                <Alert tone="warn">No tienes estudiantes activos asociados a tu cuenta.</Alert>
            )}
            {catalogo.isSuccess && (
                <div className="grid gap-5 lg:grid-cols-2">
                    {catalogo.data.reportes.map((r) => (
                        <TarjetaReporte key={r.clave} reporte={r} opciones={catalogo.data.opciones} />
                    ))}
                </div>
            )}
        </>
    )
}
