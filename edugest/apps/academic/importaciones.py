"""
Importación masiva de estudiantes y asignaciones docentes desde Excel (.xlsx) o CSV.

Flujo (dos pasos, igual que la carga de notas):
1. El administrador descarga la plantilla: trae listas desplegables con los paralelos,
   representantes, docentes y asignaturas válidos.
2. Sube el archivo -> el sistema devuelve una VISTA PREVIA fila por fila (no guarda nada).
3. Si no hay errores, confirma -> se registran todas las filas en una sola transacción.
   Si alguna fila tiene error, no se guarda ninguna (todo o nada).

Cada fila se valida con el MISMO serializer que usa el formulario manual, así se aplican
las mismas reglas: paralelo activo y de grado habilitado, representante/docente activo
con su rol, asignatura activa y un solo docente por asignatura en cada paralelo.
Las filas que ya existen en el sistema se marcan como «omitidas» (se puede volver a subir
el mismo archivo sin duplicar registros).
"""

import unicodedata
from io import BytesIO

from django.db import IntegrityError, transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from rest_framework.exceptions import ValidationError

from apps.grades.mapeo import filas_csv
from apps.security.models import Role, User

from .grados import grado_maximo, grado_minimo
from .models import AsignacionDocente, Asignatura, Estudiante, Paralelo
from .serializers import AsignacionDocenteSerializer, EstudianteSerializer

TAMANO_MAXIMO = 2 * 1024 * 1024  # 2 MB
MAX_FILAS = 500
FILAS_ENCABEZADO = 10  # el encabezado se busca en las primeras filas
CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

OK, OMITIDA, ERROR = "ok", "omitida", "error"
MENSAJE_CON_ERRORES = "El archivo tiene filas con errores. Corrígelas y vuelve a subirlo; no se guardó nada."


def normalizar(valor):
    """Minúsculas, sin tildes y con un solo espacio: «Séptimo  EGB» == «septimo egb»."""
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode()
    return " ".join(texto.lower().split())


# ---------------------------------------------------------------------------
# Configuración de cada importación
# ---------------------------------------------------------------------------
ESTUDIANTES = {
    "clave": "estudiantes",
    "hoja": "Estudiantes",
    "columnas": [  # (campo, encabezado de la plantilla, alias aceptados, obligatoria)
        ("nombres", "Nombres", {"nombres", "nombre", "nombres del estudiante"}, True),
        ("apellidos", "Apellidos", {"apellidos", "apellido", "apellidos del estudiante"}, True),
        ("grado", "Grado", {"grado", "ano", "año", "ano de basica", "nivel"}, False),
        ("paralelo", "Paralelo", {"paralelo", "curso", "grado y paralelo", "seccion"}, True),
        ("representante", "Correo del representante",
         {"correo del representante", "correo representante", "email del representante",
          "email representante", "representante", "correo", "email"}, True),
    ],
    "ejemplo": ["Luis Martín", "Pérez Intriago", None, "Séptimo EGBM A", "representante@correo.com"],
}

ASIGNACIONES = {
    "clave": "asignaciones",
    "hoja": "Asignaciones",
    "columnas": [
        ("docente", "Correo del docente",
         {"correo del docente", "correo docente", "email del docente", "email docente", "docente",
          "profesor", "correo", "email"}, True),
        ("grado", "Grado", {"grado", "ano", "año", "ano de basica", "nivel"}, False),
        ("paralelo", "Paralelo", {"paralelo", "curso", "grado y paralelo", "seccion"}, True),
        ("asignatura", "Asignatura", {"asignatura", "materia", "area"}, True),
    ],
    "ejemplo": ["docente@correo.com", None, "Séptimo EGBM A", "Matemática"],
}


# ---------------------------------------------------------------------------
# Catálogos válidos (también alimentan las listas desplegables de la plantilla)
# ---------------------------------------------------------------------------
def _paralelos():
    return list(
        Paralelo.objects.filter(
            is_active=True, grado__orden__gte=grado_minimo(), grado__orden__lte=grado_maximo()
        ).select_related("grado").order_by("grado__orden", "nombre")
    )


def _usuarios(rol):
    return list(User.objects.filter(role=rol, is_active=True).order_by("last_name", "first_name"))


def _asignaturas():
    return list(Asignatura.objects.filter(is_active=True).order_by("nombre"))


def exigir_requisitos(config):
    """Misma regla que el formulario: sin representante/docente no se puede registrar."""
    if config is ESTUDIANTES and not User.objects.filter(role=Role.REPRESENTANTE, is_active=True).exists():
        raise ValidationError({"archivo": "Primero registra al menos un representante activo."})
    if config is ASIGNACIONES:
        if not User.objects.filter(role=Role.DOCENTE, is_active=True).exists():
            raise ValidationError({"archivo": "Primero registra al menos un docente activo."})
        if not Asignatura.objects.filter(is_active=True).exists():
            raise ValidationError({"archivo": "Primero registra al menos una asignatura activa."})
    if not _paralelos():
        raise ValidationError({"archivo": "Primero registra al menos un paralelo activo."})


# ---------------------------------------------------------------------------
# Plantilla
# ---------------------------------------------------------------------------
def generar_plantilla(config):
    wb = Workbook()
    ws = wb.active
    ws.title = config["hoja"]
    opciones = wb.create_sheet("Opciones")
    ayuda = wb.create_sheet("Instrucciones")

    cab = PatternFill("solid", fgColor="17406F")
    for col, (_, titulo, _, obligatoria) in enumerate(config["columnas"], start=1):
        c = ws.cell(row=1, column=col, value=titulo + ("" if obligatoria else " (opcional)"))
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = cab
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[c.column_letter].width = 32
    ws.freeze_panes = "A2"

    # Listas desplegables (hoja «Opciones»).
    listas = {"paralelo": [p.nombre_completo for p in _paralelos()]}
    if config is ESTUDIANTES:
        listas["representante"] = [u.email for u in _usuarios(Role.REPRESENTANTE)]
        titulos = {"paralelo": "Paralelos activos", "representante": "Correos de representantes"}
        extra = {"representante": [u.full_name for u in _usuarios(Role.REPRESENTANTE)]}
    else:
        listas["docente"] = [u.email for u in _usuarios(Role.DOCENTE)]
        listas["asignatura"] = [a.nombre for a in _asignaturas()]
        titulos = {"paralelo": "Paralelos activos", "docente": "Correos de docentes", "asignatura": "Asignaturas activas"}
        extra = {"docente": [u.full_name for u in _usuarios(Role.DOCENTE)]}

    col_opc = 1
    campos = [c[0] for c in config["columnas"]]
    for campo, valores in listas.items():
        letra = opciones.cell(row=1, column=col_opc).column_letter
        opciones.cell(row=1, column=col_opc, value=titulos[campo]).font = Font(bold=True)
        opciones.column_dimensions[letra].width = 34
        for i, v in enumerate(valores, start=2):
            opciones.cell(row=i, column=col_opc, value=v)
        if campo in extra:  # nombre al lado del correo para ubicarlo fácil
            letra_n = opciones.cell(row=1, column=col_opc + 1).column_letter
            opciones.cell(row=1, column=col_opc + 1, value="Nombre").font = Font(bold=True)
            opciones.column_dimensions[letra_n].width = 34
            for i, v in enumerate(extra[campo], start=2):
                opciones.cell(row=i, column=col_opc + 1, value=v)
        if valores:
            destino = ws.cell(row=2, column=campos.index(campo) + 1).column_letter
            dv = DataValidation(
                type="list", formula1=f"=Opciones!${letra}$2:${letra}${len(valores) + 1}",
                allow_blank=True, showErrorMessage=False,
            )
            ws.add_data_validation(dv)
            dv.add(f"{destino}2:{destino}{MAX_FILAS + 1}")
        col_opc += 3 if campo in extra else 2

    lineas = [
        f"Importación de {config['clave']} — EduGest",
        "",
        f"1. Llena la hoja «{config['hoja']}» desde la fila 2, una fila por registro.",
        "2. Usa las listas desplegables o copia los valores de la hoja «Opciones».",
        "3. El paralelo se escribe completo, por ejemplo «Séptimo EGBM A». También puedes usar"
        " la columna Grado y escribir solo la letra en Paralelo.",
        f"4. Máximo {MAX_FILAS} filas. También se acepta el archivo guardado como CSV.",
        "5. Al subirlo verás una vista previa. Si alguna fila tiene error no se guarda nada:"
        " corrige el archivo y vuelve a subirlo.",
        "6. Las filas que ya existen en el sistema se omiten automáticamente.",
    ]
    if config is ESTUDIANTES:
        lineas.append("7. Cada estudiante necesita un representante ya registrado (por su correo).")
    else:
        lineas.append("7. Cada asignatura admite un solo docente por paralelo.")
    for i, texto in enumerate(lineas, start=1):
        ayuda.cell(row=i, column=1, value=texto).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
    ayuda.column_dimensions["A"].width = 110

    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------------------
# Lectura del archivo
# ---------------------------------------------------------------------------
def _leer_filas(archivo):
    if not archivo:
        raise ValidationError({"archivo": "Adjunta el archivo Excel (.xlsx) o CSV."})
    nombre = archivo.name.lower()
    if not nombre.endswith((".xlsx", ".csv")):
        raise ValidationError({"archivo": "El archivo debe ser .xlsx o .csv."})
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError({"archivo": "El archivo supera los 2 MB."})
    if nombre.endswith(".csv"):
        return filas_csv(archivo.read())
    try:
        wb = load_workbook(archivo, data_only=True, read_only=True)
    except Exception:
        raise ValidationError({"archivo": "No se pudo leer el archivo. Revisa que sea un Excel válido."}) from None
    hoja = next((ws for ws in wb.worksheets if ws.sheet_state == "visible"), wb.worksheets[0])
    filas = []
    for fila in hoja.iter_rows(values_only=True):
        filas.append(list(fila))
        if len(filas) > MAX_FILAS + FILAS_ENCABEZADO + 50:
            break
    wb.close()
    return filas


def _celda(valor):
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return " ".join(str(valor).split())


def _ubicar_columnas(filas, config):
    """Busca la fila de encabezados y devuelve (índice de fila, {campo: índice de columna})."""
    for i, fila in enumerate(filas[:FILAS_ENCABEZADO]):
        titulos = [normalizar(_celda(v)).replace("(opcional)", "").strip() for v in fila]
        mapa = {}
        for campo, _, alias, _ in config["columnas"]:
            for j, t in enumerate(titulos):
                if t in alias and j not in mapa.values():
                    mapa[campo] = j
                    break
        if all(c in mapa for c, _, _, ob in config["columnas"] if ob):
            return i, mapa
    faltan = ", ".join(t for _, t, _, ob in config["columnas"] if ob)
    raise ValidationError(
        {"archivo": f"No se encontraron las columnas obligatorias ({faltan}). Usa la plantilla de EduGest."}
    )


class _Resolutor:
    """Convierte los textos del archivo en objetos válidos (paralelo, usuarios, asignatura)."""

    def __init__(self):
        self.paralelos = {}
        for p in _paralelos():
            self.paralelos[normalizar(p.nombre_completo)] = p
        self.usuarios = {}
        for rol in (Role.REPRESENTANTE, Role.DOCENTE):
            por_correo, por_nombre = {}, {}
            for u in _usuarios(rol):
                por_correo[u.email.lower()] = u
                por_nombre.setdefault(normalizar(u.full_name), []).append(u)
            self.usuarios[rol] = (por_correo, por_nombre)
        self.asignaturas = {normalizar(a.nombre): a for a in _asignaturas()}

    def paralelo(self, grado, paralelo):
        texto = f"{grado} {paralelo}" if grado else paralelo
        p = self.paralelos.get(normalizar(texto))
        if p is None:
            raise ValueError(f"Paralelo «{texto}» no existe, está inactivo o su grado no está habilitado.")
        return p

    def usuario(self, valor, rol, nombre_rol):
        por_correo, por_nombre = self.usuarios[rol]
        u = por_correo.get(valor.lower())
        if u is None:
            candidatos = por_nombre.get(normalizar(valor), [])
            if len(candidatos) > 1:
                raise ValueError(f"Hay varios {nombre_rol}s llamados «{valor}». Usa su correo.")
            u = candidatos[0] if candidatos else None
        if u is None:
            raise ValueError(f"No hay un {nombre_rol} activo con «{valor}».")
        return u

    def asignatura(self, valor):
        a = self.asignaturas.get(normalizar(valor))
        if a is None:
            raise ValueError(f"Asignatura «{valor}» no existe o está inactiva.")
        return a


def _errores_serializer(errores):
    mensajes = []
    for valor in errores.values():
        for m in valor if isinstance(valor, list) else [valor]:
            mensajes.append(str(m))
    return mensajes


# ---------------------------------------------------------------------------
# Validación fila por fila
# ---------------------------------------------------------------------------
def _validar_estudiante(datos, r, vistos, existentes):
    nombres, apellidos = datos["nombres"], datos["apellidos"]
    mensajes = []
    if not nombres:
        mensajes.append("Faltan los nombres.")
    if not apellidos:
        mensajes.append("Faltan los apellidos.")
    paralelo = representante = None
    try:
        paralelo = r.paralelo(datos.get("grado"), datos["paralelo"]) if datos["paralelo"] else None
        if paralelo is None:
            mensajes.append("Falta el paralelo.")
    except ValueError as e:
        mensajes.append(str(e))
    try:
        representante = (
            r.usuario(datos["representante"], Role.REPRESENTANTE, "representante")
            if datos["representante"] else None
        )
        if representante is None:
            mensajes.append("Falta el correo del representante.")
    except ValueError as e:
        mensajes.append(str(e))
    if mensajes:
        return ERROR, mensajes, None

    clave = (paralelo.id, normalizar(nombres), normalizar(apellidos))
    if clave in existentes:
        return OMITIDA, ["Ya está registrado en ese paralelo."], None
    if clave in vistos:
        return ERROR, [f"Repetido en el archivo (fila {vistos[clave]})."], None
    vistos[clave] = datos["_fila"]

    s = EstudianteSerializer(data={
        "first_name": nombres, "last_name": apellidos, "paralelo": paralelo.id, "representante": representante.id,
    })
    if not s.is_valid():
        return ERROR, _errores_serializer(s.errors), None
    datos["paralelo"] = paralelo.nombre_completo
    datos["representante"] = representante.full_name
    return OK, [], s


def _validar_asignacion(datos, r, vistos, existentes):
    mensajes = []
    docente = paralelo = asignatura = None
    for campo, falta in (("docente", "Falta el correo del docente."), ("paralelo", "Falta el paralelo."),
                         ("asignatura", "Falta la asignatura.")):
        if not datos[campo]:
            mensajes.append(falta)
    try:
        if datos["docente"]:
            docente = r.usuario(datos["docente"], Role.DOCENTE, "docente")
    except ValueError as e:
        mensajes.append(str(e))
    try:
        if datos["paralelo"]:
            paralelo = r.paralelo(datos.get("grado"), datos["paralelo"])
    except ValueError as e:
        mensajes.append(str(e))
    try:
        if datos["asignatura"]:
            asignatura = r.asignatura(datos["asignatura"])
    except ValueError as e:
        mensajes.append(str(e))
    if mensajes:
        return ERROR, mensajes, None

    clave = (paralelo.id, asignatura.id)
    actual = existentes.get(clave)
    if actual is not None:
        if actual.docente_id == docente.id and actual.is_active:
            return OMITIDA, ["La asignación ya existe."], None
        if actual.docente_id == docente.id:
            return ERROR, ["La asignación existe pero está inactiva. Reactívala desde la lista."], None
        return ERROR, [f"{asignatura.nombre} en {paralelo.nombre_completo} ya la dicta {actual.docente.full_name}."], None
    if clave in vistos:
        return ERROR, [f"Esa asignatura ya tiene docente en este paralelo (fila {vistos[clave]})."], None
    vistos[clave] = datos["_fila"]

    s = AsignacionDocenteSerializer(data={"docente": docente.id, "paralelo": paralelo.id, "asignatura": asignatura.id})
    if not s.is_valid():
        return ERROR, _errores_serializer(s.errors), None
    datos["docente"] = docente.full_name
    datos["paralelo"] = paralelo.nombre_completo
    datos["asignatura"] = asignatura.nombre
    return OK, [], s


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def importar(config, archivo, confirmar):
    """
    Devuelve la vista previa. Con confirmar=True y sin errores, además guarda todo
    en una transacción y agrega «creados» al resultado. Si hay errores no guarda nada
    (la vista responde 400 con la vista previa).
    """
    exigir_requisitos(config)
    filas = _leer_filas(archivo)
    inicio, mapa = _ubicar_columnas(filas, config)
    resolutor = _Resolutor()

    if config is ESTUDIANTES:
        existentes = {
            (paralelo_id, normalizar(n), normalizar(a))
            for paralelo_id, n, a in Estudiante.objects.values_list("paralelo_id", "first_name", "last_name")
        }
        validar = _validar_estudiante
    else:
        existentes = {
            (a.paralelo_id, a.asignatura_id): a for a in AsignacionDocente.objects.select_related("docente")
        }
        validar = _validar_asignacion

    resultado, pendientes, vistos = [], [], {}
    for numero, fila in enumerate(filas[inicio + 1:], start=inicio + 2):
        datos = {campo: _celda(fila[j]) if j < len(fila) else "" for campo, j in mapa.items()}
        if not any(datos.values()):
            continue  # fila vacía
        if len(resultado) >= MAX_FILAS:
            raise ValidationError({"archivo": f"El archivo supera las {MAX_FILAS} filas. Divídelo en partes."})
        datos["_fila"] = numero
        estado, mensajes, serializer = validar(datos, resolutor, vistos, existentes)
        if serializer is not None:
            pendientes.append(serializer)
        datos.pop("_fila")
        datos.pop("grado", None)
        resultado.append({"fila": numero, "estado": estado, "mensajes": mensajes, "datos": datos})

    if not resultado:
        raise ValidationError({"archivo": "El archivo no tiene filas con datos."})

    resumen = {
        "total": len(resultado),
        "validas": sum(f["estado"] == OK for f in resultado),
        "omitidas": sum(f["estado"] == OMITIDA for f in resultado),
        "errores": sum(f["estado"] == ERROR for f in resultado),
        "filas": resultado,
        "creados": 0,
    }
    if confirmar and not resumen["errores"]:
        try:
            with transaction.atomic():
                for s in pendientes:
                    s.save()
        except IntegrityError:  # otro usuario registró lo mismo mientras tanto
            raise ValidationError(
                {"archivo": "Algunos registros se crearon mientras importabas. Vuelve a subir el archivo."}
            ) from None
        resumen["creados"] = len(pendientes)
    return resumen
