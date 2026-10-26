"""
Utilidades comunes de los comandos `seed_*`.

Los datos NO viven en el código: cada comando lee un archivo JSON (por defecto en
`edugest/seed_data/`, o el que se indique con --archivo) y valida cada registro con las
mismas reglas del modelo (full_clean) antes de guardar. Si algo falla, no se guarda nada.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError

from .grados import grado_maximo, grado_minimo, orden_habilitado
from .models import Grado

CARPETA_SEED = Path(settings.BASE_DIR) / "seed_data"


def agregar_opcion_archivo(parser, nombre_por_defecto):
    parser.add_argument(
        "--archivo",
        default=str(CARPETA_SEED / nombre_por_defecto),
        help=f"Ruta del JSON con los datos (por defecto: seed_data/{nombre_por_defecto}).",
    )


def agregar_opcion_grado(parser):
    parser.add_argument(
        "--grado",
        type=int,
        default=None,
        help="Orden del grado donde cargar (1 a 10). Por defecto, el último habilitado en .env "
        "(GRADO_MAXIMO_HABILITADO). Debe estar entre GRADO_MINIMO_HABILITADO y GRADO_MAXIMO_HABILITADO.",
    )


def leer_json(ruta):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise CommandError(f"No se encontró el archivo de datos: {ruta}")
    try:
        with ruta.open(encoding="utf-8") as archivo:
            return json.load(archivo)
    except json.JSONDecodeError as exc:
        raise CommandError(f"{ruta.name} no es un JSON válido (línea {exc.lineno}): {exc.msg}")


def lista(datos, clave, origen):
    """Devuelve datos[clave] si es una lista; si no, error claro."""
    valor = datos.get(clave) if isinstance(datos, dict) else None
    if not isinstance(valor, list):
        raise CommandError(f"{origen}: se esperaba una lista en «{clave}».")
    return valor


def texto(registro, clave, ubicacion, errores):
    valor = registro.get(clave) if isinstance(registro, dict) else None
    if not isinstance(valor, str) or not valor.strip():
        errores.append(f"{ubicacion}: falta «{clave}» o está vacío.")
        return None
    return " ".join(valor.split())


def validar_modelo(instancia, ubicacion, errores):
    """Aplica las validaciones del modelo (longitudes, opciones, rangos) sin tocar la BD."""
    try:
        instancia.full_clean(validate_unique=False, validate_constraints=False)
    except ValidationError as exc:
        for campo, mensajes in exc.message_dict.items():
            errores.append(f"{ubicacion} · {campo}: {' '.join(mensajes)}")


def abortar_si_hay_errores(errores, origen):
    if errores:
        detalle = "\n  - ".join(errores)
        raise CommandError(f"{origen} tiene {len(errores)} error(es); no se guardó nada:\n  - {detalle}")


def grado_destino(orden):
    """Grado donde se cargan los ejemplos: el indicado o el último habilitado."""
    orden = orden or grado_maximo()
    if not orden_habilitado(orden):
        raise CommandError(
            f"El grado {orden} no está habilitado (rango: {grado_minimo()} a {grado_maximo()}). "
            "Ajusta GRADO_MINIMO_HABILITADO / GRADO_MAXIMO_HABILITADO en .env o usa otro --grado."
        )
    grado = Grado.objects.filter(orden=orden).first()
    if grado is None:
        raise CommandError(f"No existe el grado de orden {orden}. Ejecuta primero: seed_academico")
    return grado
