"""
Importación de notas desde un Excel o CSV cualquiera, con mapeo inteligente (mejora 12).

El docente puede subir su propia planilla (no la de EduGest). El sistema:
1. Busca la fila de encabezados en las primeras filas.
2. Detecta la columna (o columnas) del nombre: «Estudiante», «Alumno», «Apellidos y
   nombres», o «Apellidos» + «Nombres» por separado.
3. Detecta las columnas de nota por su título («Nota», «Calificación», «Promedio»…) o,
   si no tienen título reconocible, por su contenido (números de 0 a 10).
4. Busca cada nombre en la nómina del paralelo (coincidencia.py) y devuelve una VISTA
   PREVIA con la confianza de cada coincidencia. No guarda nada.
Si hay varias columnas de nota, se propone la más probable y el docente puede elegir otra.
"""

import csv
import io
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from .coincidencia import Ambiguo, Nomina, NoEncontrado, mensaje_error, normalizar

FILAS_A_REVISAR = 15

_NOMBRE_COMPLETO = {"estudiante", "estudiantes", "alumno", "alumna", "alumnos", "nombre", "nomina",
                    "nombres y apellidos", "apellidos y nombres", "nombre completo", "nombres completos"}
_APELLIDOS = {"apellido", "apellidos"}
_NOMBRES = {"nombres"}
_NOTA = ("nota", "calificacion", "calif", "puntaje", "puntuacion", "promedio", "total", "valor", "equivalente")
_PREFERIDAS = ("final", "promedio", "total")
_DESCARTAR = ("cedula", "codigo", "id", "n", "no", "nro", "num", "numero", "orden", "fecha", "observacion")


def _texto(valor):
    return " ".join(normalizar(valor).split()) if valor is not None else ""


def _nota(valor):
    """Decimal 0–10, None si está vacía. Lanza ValueError si no es válida."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    try:
        nota = Decimal(str(valor).strip().replace(",", "."))
    except InvalidOperation:
        raise ValueError("no es un número") from None
    if nota.is_nan() or not Decimal("0") <= nota <= Decimal("10"):
        raise ValueError("debe estar entre 0 y 10")
    return nota.quantize(Decimal("0.01"))


def _es_numero(valor):
    try:
        return _nota(valor) is not None
    except ValueError:
        return False


# --------------------------------------------------------------------------- lectura
def filas_xlsx(wb):
    hoja = wb.worksheets[0]
    for ws in wb.worksheets:
        if ws.sheet_state == "visible":
            hoja = ws
            break
    return [list(f) for f in hoja.iter_rows(values_only=True)]


def filas_csv(contenido):
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = contenido.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
    except csv.Error:
        dialecto = csv.excel
        dialecto.delimiter = ";" if texto.count(";") > texto.count(",") else ","
    return [fila for fila in csv.reader(io.StringIO(texto), dialecto)]


# --------------------------------------------------------------------------- detección
def _clasificar(titulo):
    t = _texto(titulo)
    if not t:
        return None
    if t in _NOMBRE_COMPLETO or t.startswith(("nombres y", "apellidos y")):
        return "nombre"
    if t in _APELLIDOS:
        return "apellidos"
    if t in _NOMBRES:
        return "nombres"
    palabras = t.split()
    if palabras[0] in _DESCARTAR:
        return None
    if any(p.startswith(_NOTA) for p in palabras):
        return "nota"
    return None


def _columnas_numericas(datos, ancho, excluir):
    cols = []
    for c in range(ancho):
        if c in excluir:
            continue
        valores = [f[c] for f in datos if c < len(f) and f[c] not in (None, "")]
        if valores and sum(_es_numero(v) for v in valores) / len(valores) >= 0.7:
            cols.append(c)
    return cols


def detectar(filas):
    """Devuelve el mapeo: fila de encabezado, columnas de nombre y columnas de nota."""
    ancho = max((len(f) for f in filas), default=0)
    mejor = None
    for i, fila in enumerate(filas[:FILAS_A_REVISAR]):
        tipos = {c: _clasificar(v) for c, v in enumerate(fila)}
        nombre = [c for c, t in tipos.items() if t == "nombre"]
        apellidos = [c for c, t in tipos.items() if t == "apellidos"]
        nombres = [c for c, t in tipos.items() if t == "nombres"]
        cols_nombre = nombre[:1] or (apellidos[:1] + nombres[:1])
        if not cols_nombre:
            continue
        notas = [c for c, t in tipos.items() if t == "nota"]
        datos = filas[i + 1:]
        if not notas:
            notas = _columnas_numericas(datos, ancho, set(cols_nombre))
        if notas:
            mejor = (i, cols_nombre, notas)
            break

    if mejor is None:
        # Sin encabezados reconocibles: primera columna con texto + columnas numéricas.
        textuales = [
            c for c in range(ancho)
            if sum(isinstance(f[c], str) and bool(normalizar(f[c]).strip()) for f in filas if c < len(f))
            >= max(1, len(filas) // 2)
        ]
        if not textuales:
            return None
        notas = _columnas_numericas(filas, ancho, {textuales[0]})
        if not notas:
            return None
        mejor = (None, [textuales[0]], notas)

    fila_enc, cols_nombre, cols_nota = mejor
    encabezado = filas[fila_enc] if fila_enc is not None else []

    def titulo(c):
        v = encabezado[c] if c < len(encabezado) else None
        return str(v).strip() if v not in (None, "") else f"Columna {c + 1}"

    def prioridad(c):
        t = _texto(titulo(c))
        return (0 if any(p in t for p in _PREFERIDAS) else 1, -c)

    sugerida = sorted(cols_nota, key=prioridad)[0]
    return {
        "fila_encabezado": fila_enc,
        "columnas_nombre": cols_nombre,
        "titulos_nombre": [titulo(c) for c in cols_nombre],
        "columnas_nota": [{"indice": c, "titulo": titulo(c)} for c in cols_nota],
        "columna_nota": sugerida,
    }


# --------------------------------------------------------------------------- importación
def importar_tabla(filas, estudiantes, columna_nota=None):
    filas = [f for f in filas if any(v not in (None, "") for v in f)]
    mapeo = detectar(filas)
    if mapeo is None:
        raise ValidationError(
            {"archivo": "No se encontraron una columna de nombres y otra de notas. "
                        "Revisa el archivo o usa la plantilla de EduGest."}
        )
    if columna_nota is not None:
        if columna_nota not in [c["indice"] for c in mapeo["columnas_nota"]]:
            raise ValidationError({"columna_nota": "Esa columna no contiene notas."})
        mapeo["columna_nota"] = columna_nota

    nomina = Nomina(estudiantes)
    inicio = 0 if mapeo["fila_encabezado"] is None else mapeo["fila_encabezado"] + 1
    col_nota = mapeo["columna_nota"]
    filas_ok, errores, vistos, sin_nota = [], [], {}, 0

    for n, fila in enumerate(filas[inicio:], start=inicio + 1):
        partes = [str(fila[c]).strip() for c in mapeo["columnas_nombre"] if c < len(fila) and fila[c] not in (None, "")]
        nombre = " ".join(partes)
        celda = fila[col_nota] if col_nota < len(fila) else None
        if not nombre:
            continue
        try:
            nota = _nota(celda)
        except ValueError as exc:
            errores.append({"fila": n, "mensaje": f"Nota de «{nombre}»: {exc}."})
            continue
        if nota is None:
            sin_nota += 1
            continue
        try:
            est_id, est_nombre, confianza = nomina.buscar(nombre)
        except (Ambiguo, NoEncontrado) as exc:
            errores.append({"fila": n, "mensaje": mensaje_error(nombre, exc)})
            continue
        if est_id in vistos:
            errores.append({"fila": n, "mensaje": f"{est_nombre} aparece más de una vez (fila {vistos[est_id]})."})
            continue
        vistos[est_id] = n
        filas_ok.append(
            {
                "estudiante": est_id,
                "estudiante_nombre": est_nombre,
                "valor": str(nota),
                "confianza": confianza,
                "texto_original": nombre,
            }
        )

    return {"modo": "mapeo", "mapeo": mapeo, "filas": filas_ok, "errores": errores, "sin_nota": sin_nota}
