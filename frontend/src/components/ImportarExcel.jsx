import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { FileDown, FileUp, Upload } from 'lucide-react'

import { api, parseApiError } from '../api/client'
import { Alert, Button, Chip, Modal } from './ui'

const ESTADOS = {
    ok: { tone: 'ok', texto: 'Lista' },
    omitida: { tone: 'warn', texto: 'Omitida' },
    error: { tone: 'danger', texto: 'Error' },
}

async function leerErrorBlob(error) {
    if (error?.response?.data instanceof Blob) {
        try {
            error.response.data = JSON.parse(await error.response.data.text())
        } catch {
            error.response.data = {}
        }
    }
    const parsed = parseApiError(error)
    return parsed.fields.archivo ?? parsed.message
}

/**
 * Importación masiva desde Excel/CSV en dos pasos: vista previa y confirmación.
 * `endpoint`: base del recurso (p. ej. /academic/estudiantes/). `columnas`: [{ campo, titulo }].
 */
export default function ImportarExcel({ endpoint, titulo, columnas, disabled, motivo }) {
    const queryClient = useQueryClient()
    const input = useRef(null)
    const [abierto, setAbierto] = useState(false)
    const [archivo, setArchivo] = useState(null)
    const [vista, setVista] = useState(null)
    const [creados, setCreados] = useState(null)
    const [error, setError] = useState('')
    const [cargando, setCargando] = useState('')

    function reiniciar() {
        setArchivo(null)
        setVista(null)
        setCreados(null)
        setError('')
        if (input.current) input.current.value = ''
    }

    function cerrar() {
        if (cargando) return
        setAbierto(false)
        reiniciar()
    }

    async function plantilla() {
        setError('')
        setCargando('plantilla')
        try {
            const res = await api.get(`${endpoint}plantilla/`, { responseType: 'blob' })
            const enlace = document.createElement('a')
            enlace.href = URL.createObjectURL(res.data)
            enlace.download = /filename="?([^";]+)"?/i.exec(res.headers['content-disposition'] ?? '')?.[1] ?? 'plantilla.xlsx'
            document.body.appendChild(enlace)
            enlace.click()
            enlace.remove()
            setTimeout(() => URL.revokeObjectURL(enlace.href), 1000)
        } catch (e) {
            setError(await leerErrorBlob(e))
        } finally {
            setCargando('')
        }
    }

    async function enviar(confirmar) {
        setError('')
        setCargando(confirmar ? 'importar' : 'revisar')
        const datos = new FormData()
        datos.append('archivo', archivo)
        datos.append('confirmar', confirmar ? 'true' : 'false')
        try {
            const { data } = await api.post(`${endpoint}importar/`, datos, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 120_000,
            })
            setVista(data)
            if (confirmar) {
                setCreados(data.creados)
                queryClient.invalidateQueries()
            }
        } catch (e) {
            if (e?.response?.data?.vista_previa) setVista(e.response.data.vista_previa)
            setError(parseApiError(e).fields.archivo ?? parseApiError(e).message)
        } finally {
            setCargando('')
        }
    }

    const puedeImportar = vista && vista.errores === 0 && vista.validas > 0 && creados === null

    return (
        <>
            <Button variant="secondary" onClick={() => setAbierto(true)} disabled={disabled} title={disabled ? motivo : undefined}>
                <FileUp className="size-5" aria-hidden="true" />
                Importar Excel
            </Button>

            <Modal
                open={abierto}
                onClose={cerrar}
                title={titulo}
                size="xl"
                footer={
                    creados !== null ? (
                        <Button onClick={cerrar}>Listo</Button>
                    ) : (
                        <>
                            <Button variant="secondary" onClick={cerrar} disabled={!!cargando}>
                                Cancelar
                            </Button>
                            {!vista ? (
                                <Button onClick={() => enviar(false)} loading={cargando === 'revisar'} disabled={!archivo || !!cargando}>
                                    Revisar archivo
                                </Button>
                            ) : (
                                <Button onClick={() => enviar(true)} loading={cargando === 'importar'} disabled={!puedeImportar || !!cargando}>
                                    <Upload className="size-4" aria-hidden="true" />
                                    {`Importar ${vista.validas} ${vista.validas === 1 ? 'registro' : 'registros'}`}
                                </Button>
                            )}
                        </>
                    )
                }
            >
                <div className="space-y-4">
                    {!vista && (
                        <>
                            <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-700">
                                <li>Descarga la plantilla: trae listas desplegables con los valores válidos.</li>
                                <li>Llénala en Excel (también puedes guardarla como CSV).</li>
                                <li>Súbela y revisa la vista previa antes de importar.</li>
                            </ol>
                            <Button variant="ghost" onClick={plantilla} loading={cargando === 'plantilla'} disabled={!!cargando}>
                                <FileDown className="size-4" aria-hidden="true" />
                                Descargar plantilla
                            </Button>
                            <label className="block">
                                <span className="mb-1.5 block text-sm font-bold text-ink-700">Archivo (.xlsx o .csv, máx. 2 MB)</span>
                                <input
                                    ref={input}
                                    type="file"
                                    accept=".xlsx,.csv"
                                    onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                                    className="block w-full rounded-xl border border-line bg-white px-3 py-2 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:font-bold file:text-brand-700"
                                />
                            </label>
                        </>
                    )}

                    {error && <Alert>{error}</Alert>}
                    {creados !== null && (
                        <Alert tone="ok">
                            {`Se registraron ${creados} ${creados === 1 ? 'registro' : 'registros'}.`}
                            {vista?.omitidas ? ` ${vista.omitidas} ya existían y se omitieron.` : ''}
                        </Alert>
                    )}

                    {vista && (
                        <>
                            <div className="flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-bold text-ink-700">{`${vista.total} filas:`}</span>
                                <Chip tone="ok">{`${vista.validas} listas`}</Chip>
                                {vista.omitidas > 0 && <Chip tone="warn">{`${vista.omitidas} omitidas`}</Chip>}
                                {vista.errores > 0 && <Chip tone="danger">{`${vista.errores} con error`}</Chip>}
                                {creados === null && (
                                    <button type="button" onClick={reiniciar} className="ml-auto text-xs font-bold text-brand-700 hover:underline">
                                        Elegir otro archivo
                                    </button>
                                )}
                            </div>
                            {vista.errores > 0 && creados === null && (
                                <Alert tone="warn">Corrige las filas con error en el archivo y vuelve a subirlo. No se guardará nada mientras haya errores.</Alert>
                            )}
                            <div className="max-h-[50vh] overflow-auto rounded-xl border border-line">
                                <table className="w-full text-left text-sm">
                                    <thead className="sticky top-0 bg-brand-50 text-xs font-bold text-ink-700">
                                        <tr>
                                            <th className="px-3 py-2">Fila</th>
                                            {columnas.map((c) => (
                                                <th key={c.campo} className="px-3 py-2">{c.titulo}</th>
                                            ))}
                                            <th className="px-3 py-2">Estado</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {vista.filas.map((f) => (
                                            <tr key={f.fila} className="border-t border-line align-top">
                                                <td className="px-3 py-2 text-ink-500">{f.fila}</td>
                                                {columnas.map((c) => (
                                                    <td key={c.campo} className="px-3 py-2">{f.datos[c.campo] || '—'}</td>
                                                ))}
                                                <td className="px-3 py-2">
                                                    <Chip tone={ESTADOS[f.estado].tone}>{ESTADOS[f.estado].texto}</Chip>
                                                    {f.mensajes.map((m) => (
                                                        <p key={m} className={f.estado === 'error' ? 'mt-1 text-xs text-danger-600' : 'mt-1 text-xs text-ink-500'}>
                                                            {m}
                                                        </p>
                                                    ))}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </>
                    )}
                </div>
            </Modal>
        </>
    )
}
