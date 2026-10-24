"""
Configuración SOLO para ejecutar las pruebas (ubicación: edugest/test_settings.py).

    python manage.py test apps --settings=edugest.test_settings

Qué cambia respecto a settings.py:
- Usa un hasher de contraseñas rápido. Argon2 está diseñado para ser lento (unas décimas de
  segundo por contraseña) y las pruebas crean varios usuarios en cada caso, lo que volvía la
  suite 80 veces más lenta.
- Silencia los avisos de nivel WARNING: las pruebas provocan a propósito respuestas 400, 401,
  403, 404 y 405, y Django las registraría como advertencias aunque todo vaya bien.

NUNCA uses este archivo para ejecutar el servidor ni en producción.
"""

import logging

from .settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

logging.disable(logging.WARNING)

# Las pruebas existentes usan grados altos (7.º y 8.º); la restricción se prueba aparte.
GRADO_MINIMO_HABILITADO = 1
GRADO_MAXIMO_HABILITADO = 10
