"""
Comprobación al arrancar Django (`manage.py check`, `runserver`, `migrate`…).

Si el modelo de spaCy no está instalado, el PLN sigue funcionando con el respaldo por
reglas, pero con menos precisión. Sin esta comprobación el problema solo aparecía en el
log al procesar el primer texto; así se ve en cuanto se levanta el servidor.
"""

import importlib.util

from django.conf import settings
from django.core.checks import Warning, register

from .nlp import MODELO_SPACY_POR_DEFECTO


@register()
def modelo_spacy_instalado(app_configs, **kwargs):
    nombre = getattr(settings, "PLN_SPACY_MODEL", MODELO_SPACY_POR_DEFECTO)
    if not nombre:  # el PLN con spaCy se desactivó a propósito
        return []
    if importlib.util.find_spec("spacy") is None:
        faltante = "spacy"
    elif importlib.util.find_spec(nombre) is None:
        faltante = nombre
    else:
        return []
    return [
        Warning(
            f"No está instalado «{faltante}»: el PLN funcionará solo con reglas (motor «reglas»).",
            hint="Ejecuta: pip install -r requirements.txt",
            id="edugest.W001",
        )
    ]
