import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, FileDown, FileUp, History, Save } from 'lucide-react'

import { api, parseApiError } from '../../api/client'
import { Alert, Button, Card, Chip, PageHeader, SelectField, Spinner } from '../../components/ui'
import { formatFecha, hoyISO } from '../../lib/dates'
import { LeyendaSemaforo, NivelChip } from '../../components/Semaforo'
import { formatNota, nivelNota } from '../../lib/format'
import { useActividad, useNotasActividad, useParalelos, useTemasActivos } from '../../lib/queries'
import { AdjuntosActividad, EntregaEstudiante } from '../../components/ArchivosActividad'
import { useEntregasPorEstudiante } from '../../lib/archivos'

/** Convierte «8,5» o «8.5» en un número válido entre 0 y 10; null si está vacío y NaN si no sirve. */
/** Borde del campo de nota según el semáforo LOEI. */
const BORDE_NIVEL = {
    DOMINA: 'border-ok-600',
    ALCANZA: 'border-brand-600',
    PROXIMO: 'border-warn-600 bg-warn-50',
    NO_ALCANZA: 'border-danger-600 bg-danger-50',
}

function leerNota(texto) {
    const t = texto.trim().replace(',', '.')
    if (t === '') return null
    if (!/^\d{1,2}(\.\d{1,2})?$/.test(t)) return NaN
    const n = Number(t)
    return n >= 0 && n <= 10 ? n : NaN
}

export default function Calificar() {
    const { id } = useParams()
    const qc = useQueryClient()
    const actividad = useActividad(id)
    const entregas = useEntregasPorEstudiante(actividad.data)
    const notas = useNotasActividad(id)
    const paralelos = useParalelos()
    const temas = useTemasActivos()

    const [valores, setValores] = useState({}) // estudianteId -> texto
    const [tema, setTema] = useState('')
    const [result, setResult] = useState(null)
    const [err, setErr] = useState(null)
    const [historial, setHistorial] = useState(null) // id de la calificación abierta
    const [importado, setImportado] = useState(null) // vista previa del Excel
    const [excelError, setExcelError] = useState('')
    const [descargando, setDescargando] = useState(false)
    const archivoRef = useRef(null)
    const [ultimoArchivo, setUltimoArchivo] = useState(null) // para cambiar la columna de nota
    const [textoNotas, setTextoNotas] = useState('')

    // Mejora 9: plantilla Excel fija.
    async function descargarPlantilla() {
        setExcelError('')
        setDescargando(true)
        try {
            const res = await api.get(`/grades/actividades/${id}/calificaciones/plantilla/`, { responseType: 'blob' })
            const nombre = /filename="([^"]+)"/.exec(res.headers['content-disposition'] ?? '')?.[1] ?? 'plantilla_notas.xlsx'
            const url = URL.createObjectURL(res.data)
            const enlace = document.createElement('a')
            enlace.href = url
            enlace.download = nombre
            enlace.click()
            URL.revokeObjectURL(url)
        } catch {
            setExcelError('No se pudo descargar la plantilla. Intenta de nuevo.')
        } finally {
            setDescargando(false)
        }
    }

    // Vista previa (Excel, CSV o texto): solo llena el formulario; el docente revisa y guarda.
    function aplicarVistaPrevia(data) {
        setValores((v) => ({ ...v, ...Object.fromEntries(data.filas.map((f) => [f.estudiante, formatNota(f.valor)])) }))
        setImportado(data)
    }

    const importar = useMutation({
        mutationFn: async ({ archivo, columna }) => {
            const datos = new FormData()
            datos.append('archivo', archivo)
            if (columna != null) datos.append('columna_nota', String(columna))
            // Sin esta cabecera, axios convertiría el FormData a JSON (el cliente usa JSON por defecto).
            return (
                await api.post(`/grades/actividades/${id}/calificaciones/importar/`, datos, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                })
            ).data
        },
        onMutate: () => {
            setExcelError('')
            setImportado(null)
            setResult(null)
        },
        onSuccess: (data, { archivo }) => {
            setUltimoArchivo(archivo)
            aplicarVistaPrevia(data)
        },
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setExcelError(fields.archivo ?? fields.columna_nota ?? message)
        },
        onSettled: () => {
            if (archivoRef.current) archivoRef.current.value = ''
        },
    })

    // Mejora 13: notas desde texto libre («Vera 9, Gómez 4,5»).
    const interpretar = useMutation({
        mutationFn: async () => (await api.post(`/grades/actividades/${id}/calificaciones/texto/`, { texto: textoNotas })).data,
        onMutate: () => {
            setExcelError('')
            setImportado(null)
            setResult(null)
        },
        onSuccess: aplicarVistaPrevia,
        onError: (e) => {
            const { message, fields } = parseApiError(e)
            setExcelError(fields.texto ?? message)
        },
    })

    // Evaluación de refuerzo: estudiantes con plan completado esperando esta nota.
    const esEvaluacion = !!actividad.data?.es_evaluacion_refuerzo
    const pendientes = useQuery({
        queryKey: ['planes', { evaluacion: 'pendiente', paralelo: actividad.data?.paralelo, asignatura: actividad.data?.asignatura }],
        queryFn: async () =>
            (await api.get('/reinforcement/planes/', {
                params: { evaluacion: 'pendiente', paralelo: actividad.data.paralelo, asignatura: actividad.data.asignatura },
            })).data,
        enabled: esEvaluacion,
    })
    const porEvaluar = useMemo(
        () =>
            Object.fromEntries(
                (pendientes.data?.results ?? []).map((p) => [p.estudiante, p.temas.filter((t) => t.superado == null).map((t) => t.tema_nombre)]),
            ),
        [pendientes.data],
    )

    // Carga en los campos las notas ya registradas.
    useEffect(() => {
        if (!notas.data) return
        setValores(Object.fromEntries(notas.data.calificaciones.map((f) => [f.estudiante, f.valor != null ? formatNota(f.valor) : ''])))
        setTema((t) => t || String(notas.data.calificaciones.find((f) => f.tema)?.tema ?? ''))
    }, [notas.data])

    const grado = paralelos.data?.find((p) => p.id === actividad.data?.paralelo)?.grado
    const temasDeLaActividad = useMemo(
        () => (temas.data ?? []).filter((t) => t.asignatura === actividad.data?.asignatura && t.grado === grado),
        [temas.data, actividad.data, grado],
    )

    const save = useMutation({
        mutationFn: async () => {
            const calificaciones = Object.entries(valores)
                .map(([estudiante, texto]) => ({ estudiante: Number(estudiante), valor: leerNota(texto) }))
                .filter((c) => c.valor !== null)
            return (await api.post(`/grades/actividades/${id}/calificaciones/`, { tema: Number(tema), calificaciones })).data
        },
        onSuccess: (data) => {
            setResult(data)
            setErr(null)
            setImportado(null)
            qc.invalidateQueries({ queryKey: ['notas-actividad', id] })
            qc.invalidateQueries({ queryKey: ['planes'] })
            qc.invalidateQueries({ queryKey: ['plan'] })
            qc.invalidateQueries({ queryKey: ['dificultades'] })
        },
        onError: (e) => {
            setResult(null)
            setErr(parseApiError(e))
        },
    })

    if (actividad.isLoading || notas.isLoading) return <Spinner />
    if (actividad.isError || notas.isError) {
        return <Alert>No se encontró la actividad o no tienes acceso a ella.</Alert>
    }

    const a = actividad.data
    const { resumen, calificaciones: filas } = notas.data
    const cancelada = a.estado === 'CANCELADA'
    const temprano = a.fecha_entrega > hoyISO()
    const bloqueada = cancelada || temprano

    const invalidas = filas.filter((f) => Number.isNaN(leerNota(valores[f.estudiante] ?? '')))
    const llenas = filas.filter((f) => leerNota(valores[f.estudiante] ?? '') !== null && !Number.isNaN(leerNota(valores[f.estudiante] ?? '')))
    const puedeGuardar = !bloqueada && !!tema && llenas.length > 0 && invalidas.length === 0
    const detectadas = result?.dificultades.filter((d) => d.estado === 'DETECTADA') ?? []
    // Coincidencias aproximadas del Excel o del texto que el docente debe confirmar.
    const verificar = Object.fromEntries(
        (importado?.filas ?? []).filter((f) => f.confianza === 'media').map((f) => [f.estudiante, f.texto_original]),
    )

    return (
        <>
            <Link to="/docente/actividades" className="mb-4 inline-flex items-center gap-1.5 text-sm font-bold text-brand-700 hover:underline">
                <ArrowLeft className="size-4" aria-hidden="true" />
                Volver a actividades
            </Link>
            <PageHeader
                title={`Calificar ${a.asignatura_nombre}`}
                subtitle={`${a.paralelo_nombre} · Entrega: ${formatFecha(a.fecha_entrega)}`}
            />

            <div className="mb-5 max-w-3xl rounded-xl bg-white px-4 py-3">
                <p className="whitespace-pre-line text-ink-700">{a.descripcion}</p>
                <AdjuntosActividad actividad={a} />
            </div>

            {esEvaluacion && (
                <Alert tone="ok" className="mb-5 max-w-3xl">
                    <p>Evaluación de refuerzo</p>
                    <p className="mt-1 font-normal">
                        La nota que registres en el tema evaluado cerrará los planes completados de cada estudiante: se supera si el promedio del tema llega a 7,00 (o si la nota es de 7,00 o más en un refuerzo pedido por el docente).
                        {pendientes.isSuccess && (pendientes.data.count === 0 ? ' Ningún estudiante tiene planes pendientes de evaluación en esta asignatura.' : ` Estudiantes por evaluar: ${pendientes.data.count}.`)}
                    </p>
                </Alert>
            )}
            {cancelada && <Alert tone="warn" className="mb-5">Esta actividad fue cancelada y no se puede calificar.</Alert>}
            {temprano && !cancelada && (
                <Alert tone="warn" className="mb-5">Podrás calificar desde el día de entrega: {formatFecha(a.fecha_entrega)}.</Alert>
            )}
            {err && <Alert className="mb-5">{err.fields.tema ?? err.fields.calificaciones ?? err.message}</Alert>}
            {result && (
                <Alert tone="ok" className="mb-5">
                    <p>
                        Notas guardadas: {result.creadas} nuevas, {result.actualizadas} corregidas, {result.sin_cambios} sin cambios.
                    </p>
                    {detectadas.length > 0 && (
                        <p className="mt-1 font-normal">
                            Dificultades detectadas:{' '}
                            {detectadas.map((d) => `${d.estudiante_nombre} en ${d.tema_nombre} (${d.nivel === 'ALTA' ? 'alta' : 'moderada'})`).join('; ')}.
                        </p>
                    )}
                </Alert>
            )}

            <Card className="mb-5 max-w-3xl">
                <SelectField
                    label="Tema evaluado"
                    value={tema}
                    onChange={(e) => setTema(e.target.value)}
                    disabled={bloqueada}
                    hint="Las notas se registran sobre este tema y sirven para detectar dificultades."
                >
                    <option value="">Selecciona un tema</option>
                    {temasDeLaActividad.map((t) => (
                        <option key={t.id} value={t.id}>{t.padre_nombre ? `${t.padre_nombre} › ${t.nombre}` : t.nombre}</option>
                    ))}
                </SelectField>
                {temas.isSuccess && temasDeLaActividad.length === 0 && (
                    <Alert tone="warn" className="mt-3">Esta asignatura no tiene temas para el grado. Pide al administrador que los registre.</Alert>
                )}
            </Card>

            <Card className="mb-5 max-w-3xl">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0 flex-1 basis-60">
                        <p className="font-bold text-navy-800">Cargar notas desde Excel o CSV</p>
                        <p className="text-sm text-ink-500">Usa la plantilla o sube tu propia planilla: se detectan las columnas de nombre y nota. Podrás revisar antes de guardar.</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                        <Button variant="secondary" onClick={descargarPlantilla} loading={descargando}>
                            <FileDown className="size-4" aria-hidden="true" />
                            Plantilla
                        </Button>
                        <Button variant="secondary" onClick={() => archivoRef.current?.click()} loading={importar.isPending} disabled={bloqueada}>
                            <FileUp className="size-4" aria-hidden="true" />
                            Subir archivo
                        </Button>
                        <input
                            ref={archivoRef}
                            type="file"
                            accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                            className="sr-only"
                            aria-label="Archivo Excel o CSV con las notas"
                            onChange={(e) => e.target.files?.[0] && importar.mutate({ archivo: e.target.files[0] })}
                        />
                    </div>
                </div>
                <div className="mt-4 border-t border-line pt-4">
                    <label htmlFor="texto-notas" className="font-bold text-navy-800">Pegar notas en texto</label>
                    <p className="text-sm text-ink-500">Ejemplo: «Vera 9, Gómez 4,5, Morales 7» o una nota por línea.</p>
                    <textarea
                        id="texto-notas"
                        rows={3}
                        maxLength={5000}
                        value={textoNotas}
                        onChange={(e) => setTextoNotas(e.target.value)}
                        disabled={bloqueada}
                        className="mt-2 block w-full rounded-xl border border-line bg-white px-3.5 py-2.5 text-[15px] hover:border-ink-300"
                    />
                    <div className="mt-2 flex justify-end">
                        <Button variant="secondary" onClick={() => interpretar.mutate()} loading={interpretar.isPending} disabled={bloqueada || !textoNotas.trim()}>
                            Interpretar notas
                        </Button>
                    </div>
                </div>
                {excelError ? <Alert className="mt-3">{excelError}</Alert> : null}
                {importado ? (
                    <Alert tone={importado.errores.length ? 'warn' : 'ok'} className="mt-3">
                        <p>
                            {`Se cargaron ${importado.filas.length} ${importado.filas.length === 1 ? 'nota' : 'notas'} ${importado.modo === 'texto' ? 'desde el texto' : 'desde el archivo'}`}
                            {importado.sin_nota ? ` (${importado.sin_nota} sin nota)` : ''}
                            {'. Revisa, elige el tema y pulsa «Guardar notas».'}
                        </p>
                        {importado.modo === 'mapeo' ? (
                            <div className="mt-2 flex flex-wrap items-center gap-2 font-normal">
                                <span>{`Nombre: «${importado.mapeo.titulos_nombre.join(' + ')}» · Nota:`}</span>
                                {importado.mapeo.columnas_nota.length > 1 ? (
                                    <select
                                        aria-label="Columna de la nota"
                                        value={importado.mapeo.columna_nota}
                                        disabled={importar.isPending || !ultimoArchivo}
                                        onChange={(e) => importar.mutate({ archivo: ultimoArchivo, columna: Number(e.target.value) })}
                                        className="min-h-9 rounded-lg border border-line bg-white px-2 text-sm"
                                    >
                                        {importado.mapeo.columnas_nota.map((c) => (
                                            <option key={c.indice} value={c.indice}>{c.titulo}</option>
                                        ))}
                                    </select>
                                ) : (
                                    <span>{`«${importado.mapeo.columnas_nota[0].titulo}»`}</span>
                                )}
                            </div>
                        ) : null}
                        {importado.filas.some((f) => f.confianza === 'media') ? (
                            <p className="mt-1 font-normal">Revisa los nombres marcados con «Verifica»: se reconocieron con una coincidencia aproximada.</p>
                        ) : null}
                        {importado.errores.length > 0 ? (
                            <ul className="mt-1 list-disc pl-5 font-normal">
                                {importado.errores.map((e) => (
                                    <li key={`${e.fila}-${e.mensaje}`}>{e.fila ? `Fila ${e.fila}: ${e.mensaje}` : e.mensaje}</li>
                                ))}
                            </ul>
                        ) : null}
                    </Alert>
                ) : null}
            </Card>

            <LeyendaSemaforo className="mb-3 max-w-3xl" />
            <p className="mb-2 text-sm text-ink-500">
                {resumen.calificados} de {resumen.estudiantes} calificados
                {resumen.promedio != null && ` · Promedio del paralelo: ${formatNota(resumen.promedio)}`}
                {a.modalidad_entrega === 'APP' && !entregas.cargando ? ` · Entregas en la app: ${entregas.entregadas} de ${entregas.total}` : ''}
            </p>

            <ul className="max-w-3xl divide-y divide-line overflow-hidden rounded-2xl border border-line bg-white">
                {filas.map((f) => {
                    const texto = valores[f.estudiante] ?? ''
                    const malo = Number.isNaN(leerNota(texto))
                    // Semáforo en tiempo real: el nivel cambia mientras el docente escribe la nota.
                    const valor = malo ? null : leerNota(texto)
                    const nivel = nivelNota(valor)
                    return (
                        <li key={f.estudiante} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 sm:px-5">
                            <div className="min-w-0 flex-1 basis-48">
                                <p className="font-bold text-ink-900">{f.estudiante_nombre}</p>
                                <div className="flex flex-wrap items-center gap-2">
                                    {nivel ? <NivelChip nivel={nivel} /> : <span className="text-sm text-ink-500">Sin calificar</span>}
                                    {porEvaluar[f.estudiante] && <Chip tone="warn">Plan completado · evaluar: {porEvaluar[f.estudiante].join(', ')}</Chip>}
                                    {verificar[f.estudiante] ? <Chip tone="warn">{`Verifica: «${verificar[f.estudiante]}»`}</Chip> : null}
                                </div>
                                <EntregaEstudiante fila={entregas.mapa[f.estudiante]} />
                                {f.calificacion && (
                                    <button
                                        type="button"
                                        className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:underline"
                                        aria-expanded={historial === f.calificacion}
                                        onClick={() => setHistorial((h) => (h === f.calificacion ? null : f.calificacion))}
                                    >
                                        <History className="size-3.5" aria-hidden="true" />
                                        {historial === f.calificacion ? 'Ocultar cambios' : 'Ver cambios de la nota'}
                                    </button>
                                )}
                                {historial === f.calificacion && <HistorialNota calificacion={f.calificacion} />}
                            </div>
                            <div>
                                <label htmlFor={`nota-${f.estudiante}`} className="sr-only">Nota de {f.estudiante_nombre}</label>
                                <input
                                    id={`nota-${f.estudiante}`}
                                    inputMode="decimal"
                                    autoComplete="off"
                                    placeholder="0 – 10"
                                    disabled={bloqueada}
                                    value={texto}
                                    aria-invalid={malo ? 'true' : undefined}
                                    onChange={(e) => setValores((v) => ({ ...v, [f.estudiante]: e.target.value }))}
                                    className={`block min-h-11 w-28 rounded-xl border bg-white px-3 text-right text-[15px] font-bold disabled:bg-brand-50 ${malo ? 'border-danger-600' : BORDE_NIVEL[nivel] ?? 'border-line hover:border-ink-300'}`}
                                />
                                {malo && <p className="mt-1 text-xs font-medium text-danger-600">Entre 0 y 10</p>}
                            </div>
                        </li>
                    )
                })}
            </ul>

            <div className="mt-5 flex max-w-3xl justify-end">
                <Button variant="ok" onClick={() => save.mutate()} loading={save.isPending} disabled={!puedeGuardar}>
                    <Save className="size-4" aria-hidden="true" />
                    Guardar notas
                </Button>
            </div>
        </>
    )
}

/** Correcciones registradas de una nota (quién, cuándo, de cuánto a cuánto). */
function HistorialNota({ calificacion }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ['historial-nota', calificacion],
        queryFn: async () => (await api.get(`/grades/calificaciones/${calificacion}/historial/`)).data,
    })
    if (isLoading) return <p className="mt-1 text-xs text-ink-500">Cargando…</p>
    if (isError) return <p className="mt-1 text-xs text-danger-600">No se pudo cargar el historial.</p>
    if (data.length === 0) return <p className="mt-1 text-xs text-ink-500">La nota no ha sido corregida.</p>
    return (
        <ul className="mt-1 space-y-0.5 text-xs text-ink-500">
            {data.map((h) => (
                <li key={h.id}>
                    {new Date(h.created_at).toLocaleString('es-EC', { dateStyle: 'medium', timeStyle: 'short' })}:{' '}
                    <b className="text-ink-700">{formatNota(h.valor_anterior)} → {formatNota(h.valor_nuevo)}</b>
                    {h.tema_anterior !== h.tema_nuevo && ` · tema ${h.tema_anterior_nombre} → ${h.tema_nuevo_nombre}`}
                    {h.modificado_por_nombre && ` · ${h.modificado_por_nombre}`}
                </li>
            ))}
        </ul>
    )
}
