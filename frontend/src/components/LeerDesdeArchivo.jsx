import { useRef } from 'react'
import { useMutation } from '@tanstack/react-query'
import { FileScan } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { Alert, Button } from './ui'

const MAX_MB = 10
const TIPOS = '.pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp'
const METODOS = {
    pdf_texto: 'Texto leído del PDF.',
    pdf_ocr: 'Texto reconocido en el PDF escaneado.',
    imagen_ocr: 'Texto reconocido en la imagen.',
}

/**
 * Lee la indicación desde un PDF o una foto y la entrega al textarea para que el docente
 * la revise. No sube el archivo como adjunto: solo extrae el texto.
 */
export default function LeerDesdeArchivo({ textoActual, onTexto }) {
    const ref = useRef(null)

    const lectura = useMutation({
        mutationFn: async (archivo) => {
            if (archivo.size > MAX_MB * 1024 * 1024) throw new Error(`El archivo supera los ${MAX_MB} MB.`)
            const datos = new FormData()
            datos.append('archivo', archivo)
            const { data } = await api.post('/activities/actividades/extraer-texto/', datos, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 90_000, // el OCR de varias páginas puede tardar
            })
            return data
        },
        onSuccess: (data) => {
            const reemplazar = !textoActual.trim() || window.confirm('¿Reemplazar el texto que ya escribiste por el del archivo?')
            if (reemplazar) onTexto(data.texto)
        },
    })

    function elegir(e) {
        const archivo = e.target.files?.[0]
        e.target.value = '' // permite volver a elegir el mismo archivo
        if (archivo) lectura.mutate(archivo)
    }

    const error = lectura.isError
        ? lectura.error instanceof Error && !lectura.error.response
            ? lectura.error.message
            : (parseApiError(lectura.error).fields.archivo ?? parseApiError(lectura.error).message)
        : ''

    return (
        <div className="space-y-2">
            <input ref={ref} type="file" accept={TIPOS} className="hidden" onChange={elegir} />
            <div className="flex flex-wrap items-center gap-3">
                <Button variant="secondary" onClick={() => ref.current?.click()} loading={lectura.isPending}>
                    <FileScan className="size-4" aria-hidden="true" />
                    {lectura.isPending ? 'Leyendo archivo…' : 'Leer desde PDF o imagen'}
                </Button>
                <span className="text-sm text-ink-500">{`PDF, JPG, PNG o WEBP de hasta ${MAX_MB} MB.`}</span>
            </div>
            {error && <Alert>{error}</Alert>}
            {lectura.isSuccess && (
                <Alert tone={lectura.data.advertencias.length ? 'warn' : 'ok'}>
                    <p>{METODOS[lectura.data.metodo]} Revisa el texto antes de previsualizar.</p>
                    {lectura.data.advertencias.length > 0 && (
                        <ul className="mt-1 list-disc space-y-0.5 pl-4">
                            {lectura.data.advertencias.map((a) => (
                                <li key={a}>{a}</li>
                            ))}
                        </ul>
                    )}
                </Alert>
            )}
        </div>
    )
}
