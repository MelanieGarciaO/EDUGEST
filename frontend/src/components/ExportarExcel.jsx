import { useState } from 'react'
import { FileSpreadsheet } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { Button } from './ui'

/**
 * Descarga en Excel el listado de una pantalla aplicando sus filtros actuales.
 * `url` es el endpoint `.../exportar/`; `params` son los mismos filtros de la lista (sin `page`).
 */
export default function ExportarExcel({ url, params, archivo, disabled }) {
    const [cargando, setCargando] = useState(false)
    const [error, setError] = useState('')

    async function exportar() {
        setError('')
        setCargando(true)
        try {
            const res = await api.get(url, { params, responseType: 'blob', timeout: 120_000 })
            const nombre = /filename="?([^";]+)"?/i.exec(res.headers['content-disposition'] ?? '')?.[1] ?? archivo
            const enlace = document.createElement('a')
            enlace.href = URL.createObjectURL(res.data)
            enlace.download = nombre
            document.body.appendChild(enlace)
            enlace.click()
            enlace.remove()
            setTimeout(() => URL.revokeObjectURL(enlace.href), 1000)
        } catch (e) {
            // La respuesta de error también llega como Blob: se convierte a JSON para leer el mensaje.
            if (e?.response?.data instanceof Blob) {
                try {
                    e.response.data = JSON.parse(await e.response.data.text())
                } catch {
                    e.response.data = {}
                }
            }
            setError(parseApiError(e).message || 'No se pudo exportar el listado.')
        } finally {
            setCargando(false)
        }
    }

    return (
        <div className="flex flex-col items-end gap-1">
            <Button variant="secondary" onClick={exportar} loading={cargando} disabled={disabled || cargando}>
                <FileSpreadsheet className="size-5" aria-hidden="true" />
                Exportar Excel
            </Button>
            {error && <p role="alert" className="text-xs font-medium text-danger-600">{error}</p>}
        </div>
    )
}
