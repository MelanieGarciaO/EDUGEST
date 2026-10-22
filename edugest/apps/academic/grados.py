"""
Restricción de grados habilitados.

La versión actual del aplicativo atiende de 1.º a 4.º de EGB. Para habilitar más grados
basta con subir `GRADO_MAXIMO_HABILITADO` en el archivo .env (por ejemplo, 7 habilita hasta
Séptimo); no hace falta tocar el código ni migrar la base de datos.
"""

from django.conf import settings


def grado_maximo():
    return settings.GRADO_MAXIMO_HABILITADO


def grado_habilitado(grado):
    return grado.orden <= grado_maximo()


def mensaje_grado_no_habilitado():
    return (
        f"Por ahora el aplicativo solo está habilitado hasta el grado {grado_maximo()}.º de EGB. "
        "Este grado aún no está disponible."
    )
