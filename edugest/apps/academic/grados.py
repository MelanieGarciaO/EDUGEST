"""
Restricción de grados habilitados.

La versión actual del aplicativo atiende la EGB Media: de 5.º a 7.º (Quinto, Sexto y
Séptimo). El rango se configura en el archivo .env con `GRADO_MINIMO_HABILITADO` y
`GRADO_MAXIMO_HABILITADO`; para cambiarlo no hace falta tocar el código ni migrar la base
de datos.
"""

from django.conf import settings


def grado_minimo():
    return settings.GRADO_MINIMO_HABILITADO


def grado_maximo():
    return settings.GRADO_MAXIMO_HABILITADO


def orden_habilitado(orden):
    return grado_minimo() <= orden <= grado_maximo()


def grado_habilitado(grado):
    return orden_habilitado(grado.orden)


def mensaje_grado_no_habilitado():
    return (
        f"Por ahora el aplicativo solo está habilitado de {grado_minimo()}.º a {grado_maximo()}.º "
        "de EGB. Este grado aún no está disponible."
    )
