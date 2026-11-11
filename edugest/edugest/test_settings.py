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

# Las evidencias se guardan en memoria: las pruebas nunca tocan Supabase ni el disco.
STORAGES = {
    **STORAGES,  # noqa: F405
    "evidencias": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
}

# Base de datos para las pruebas. Por defecto es la misma del .env, pero si apunta a
# Supabase las pruebas son lentas y al final Django no puede borrar «test_postgres»
# porque el pooler deja una conexión abierta. Para evitarlo, define en el .env una
# PostgreSQL local SOLO para pruebas (Django crea y borra ahí la base «test_<nombre>»):
#   TEST_DB_HOST=localhost
#   TEST_DB_NAME=edugest
#   TEST_DB_USER=postgres
#   TEST_DB_PASSWORD=tu_password_local
#   TEST_DB_PORT=5432
if env("TEST_DB_HOST", default=""):  # noqa: F405
    DATABASES["default"].update(  # noqa: F405
        NAME=env("TEST_DB_NAME", default="edugest"),  # noqa: F405
        USER=env("TEST_DB_USER", default="postgres"),  # noqa: F405
        PASSWORD=env("TEST_DB_PASSWORD", default=""),  # noqa: F405
        HOST=env("TEST_DB_HOST"),  # noqa: F405
        PORT=env("TEST_DB_PORT", default="5432"),  # noqa: F405
        CONN_MAX_AGE=0,
        OPTIONS={"sslmode": "disable"},
    )

# Pruebas: correos en memoria (mail.outbox) y envío en el mismo hilo para poder verificarlos.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
NOTIFICACIONES_ASINCRONAS = False
