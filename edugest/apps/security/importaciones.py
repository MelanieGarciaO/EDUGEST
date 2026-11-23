"""
Importación masiva de usuarios desde Excel (.xlsx) o CSV: nombres, apellidos, correo y rol.

Flujo (igual que estudiantes y asignaciones):
1. El admin descarga la plantilla (con lista desplegable de roles).
2. Sube el archivo -> VISTA PREVIA fila por fila (no guarda nada).
3. Confirma -> si no hay errores, se registran TODOS en una sola transacción (todo o nada).

Cada usuario queda con la contraseña inutilizable y una entrada en la cola de envíos
(cola_accesos): su clave temporal se genera y se envía por correo DESPUÉS, de forma
ordenada, sin bloquear la importación ni saturar el servicio de correo.

Choques de información:
- Correos repetidos dentro del archivo: error en la fila repetida.
- Correos ya registrados: la fila se omite (se puede subir el mismo archivo sin duplicar).
- Dos administradores importando a la vez: un bloqueo de PostgreSQL (pg_advisory_xact_lock)
  hace que las importaciones se confirmen de una en una, y antes de guardar se vuelve a
  comprobar qué correos existen.
"""

from io import BytesIO

from django.db import IntegrityError, connection, transaction
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from apps.reports.excel_seguro import proteger_formulas
from rest_framework.exceptions import ValidationError

from apps.academic.importaciones import (
    CONTENT_TYPE,
    ERROR,
    MAX_FILAS,
    MENSAJE_CON_ERRORES,
    OK,
    OMITIDA,
    _celda,
    _leer_filas,
    _ubicar_columnas,
    normalizar,
)

from . import cola_accesos
from .models import Role, User
from .serializers import UserCreateSerializer

__all__ = ["CONTENT_TYPE", "MENSAJE_CON_ERRORES", "generar_plantilla", "importar"]

BLOQUEO_IMPORTACION = 7_310_001  # clave del pg_advisory_xact_lock

CONFIG = {
    "columnas": [  # (campo, encabezado, alias aceptados, obligatoria)
        ("nombres", "Nombres", {"nombres", "nombre", "first name"}, True),
        ("apellidos", "Apellidos", {"apellidos", "apellido", "last name"}, True),
        ("correo", "Correo", {"correo", "correo electronico", "email", "e-mail", "mail", "usuario"}, True),
        ("rol", "Rol", {"rol", "role", "perfil", "tipo de usuario", "cargo"}, True),
    ],
}

ROLES = {
    "docente": Role.DOCENTE, "profesor": Role.DOCENTE, "profesora": Role.DOCENTE, "maestro": Role.DOCENTE,
    "maestra": Role.DOCENTE,
    "representante": Role.REPRESENTANTE, "padre": Role.REPRESENTANTE, "madre": Role.REPRESENTANTE,
    "padre de familia": Role.REPRESENTANTE, "madre de familia": Role.REPRESENTANTE, "tutor": Role.REPRESENTANTE,
    "tutora": Role.REPRESENTANTE, "representante legal": Role.REPRESENTANTE,
    "administrador": Role.ADMINISTRADOR, "administradora": Role.ADMINISTRADOR, "admin": Role.ADMINISTRADOR,
}


# ---------------------------------------------------------------------------
# Plantilla
# ---------------------------------------------------------------------------
def generar_plantilla():
    wb = Workbook()
    ws = wb.active
    ws.title = "Usuarios"
    ayuda = wb.create_sheet("Instrucciones")

    cab = PatternFill("solid", fgColor="17406F")
    anchos = [28, 28, 36, 20]
    for col, ((_, titulo, _, _), ancho) in enumerate(zip(CONFIG["columnas"], anchos), start=1):
        c = ws.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = cab
        c.alignment = Alignment(vertical="center")
        ws.column_dimensions[c.column_letter].width = ancho
    ws.freeze_panes = "A2"

    roles = [label for _, label in Role.choices]
    dv = DataValidation(type="list", formula1='"' + ",".join(roles) + '"', allow_blank=True, showErrorMessage=False)
    ws.add_data_validation(dv)
    dv.add(f"D2:D{MAX_FILAS + 1}")

    lineas = [
        "Importación de usuarios — EduGest",
        "",
        "1. Llena la hoja «Usuarios» desde la fila 2, una fila por persona.",
        "   Ejemplo: Ana María | Pérez López | ana.perez@correo.com | Docente",
        f"2. Rol: {', '.join(roles)} (usa la lista desplegable).",
        "3. Cada correo debe ser único: es el usuario con el que la persona ingresará.",
        f"4. Máximo {MAX_FILAS} filas. También se acepta el archivo guardado como CSV.",
        "5. Al subirlo verás una vista previa. Si alguna fila tiene error no se guarda nada:",
        "   corrige el archivo y vuelve a subirlo. Los correos ya registrados se omiten.",
        "6. Al confirmar, cada usuario recibirá en su correo su propia contraseña temporal",
        "   (válida por 2 horas). Los correos se envían en cola, en los minutos siguientes.",
        "7. Nadie, ni el administrador, ve las contraseñas temporales.",
    ]
    for i, texto in enumerate(lineas, start=1):
        ayuda.cell(row=i, column=1, value=texto).font = Font(bold=(i == 1), size=13 if i == 1 else 11)
    ayuda.column_dimensions["A"].width = 100

    salida = BytesIO()
    proteger_formulas(wb)  # ningún texto (p. ej. «=HYPERLINK(...)») se guarda como fórmula
    wb.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
def _validar(datos, vistos, existentes):
    mensajes = []
    rol = ROLES.get(normalizar(datos["rol"]))
    if not datos["nombres"]:
        mensajes.append("Faltan los nombres.")
    if not datos["apellidos"]:
        mensajes.append("Faltan los apellidos.")
    if not datos["correo"]:
        mensajes.append("Falta el correo.")
    if not datos["rol"]:
        mensajes.append("Falta el rol.")
    elif rol is None:
        mensajes.append(f"Rol «{datos['rol']}» no válido. Usa Docente, Representante o Administrador.")
    if mensajes:
        return ERROR, mensajes, None

    correo = datos["correo"].strip().lower()
    if correo in existentes:
        return OMITIDA, ["Ya hay un usuario con este correo."], None
    if correo in vistos:
        return ERROR, [f"Correo repetido en el archivo (fila {vistos[correo]})."], None
    vistos[correo] = datos["_fila"]

    s = UserCreateSerializer(data={
        "first_name": datos["nombres"], "last_name": datos["apellidos"], "email": correo, "role": rol,
    })
    if not s.is_valid():
        return ERROR, [str(m) for v in s.errors.values() for m in (v if isinstance(v, list) else [v])], None
    datos["correo"] = s.validated_data["email"]
    datos["rol"] = Role(rol).label
    return OK, [], s.validated_data


def _correos_existentes():
    return {e.lower() for e in User.objects.values_list("email", flat=True)}


def importar(archivo, confirmar):
    """Vista previa; con confirmar=True y sin errores registra a todos y encola sus correos."""
    filas = _leer_filas(archivo)
    inicio, mapa = _ubicar_columnas(filas, CONFIG)
    existentes = _correos_existentes()

    resultado, nuevos, vistos = [], [], {}
    for numero, fila in enumerate(filas[inicio + 1:], start=inicio + 2):
        datos = {campo: _celda(fila[j]) if j < len(fila) else "" for campo, j in mapa.items()}
        if not any(datos.values()):
            continue
        if len(resultado) >= MAX_FILAS:
            raise ValidationError({"archivo": f"El archivo supera las {MAX_FILAS} filas. Divídelo en partes."})
        datos["_fila"] = numero
        estado, mensajes, validos = _validar(datos, vistos, existentes)
        if validos is not None:
            nuevos.append(validos)
        datos.pop("_fila")
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
        "correos_en_cola": 0,
    }
    if confirmar and not resumen["errores"] and nuevos:
        lote = cola_accesos.nuevo_lote()
        try:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:  # una importación a la vez
                        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [BLOQUEO_IMPORTACION])
                choque = {u["email"] for u in nuevos} & _correos_existentes()
                if choque:
                    raise IntegrityError
                usuarios = [
                    User.objects.create_user(password=None, must_change_password=True, **datos)
                    for datos in nuevos
                ]
                cola_accesos.encolar(usuarios, lote)
        except IntegrityError:
            raise ValidationError({
                "archivo": "Mientras importabas se registraron algunos de estos correos. "
                "Vuelve a subir el archivo: esos usuarios aparecerán como omitidos."
            }) from None
        resumen["creados"] = len(usuarios)
        resumen["correos_en_cola"] = len(usuarios)
        resumen["lote"] = lote
    return resumen
