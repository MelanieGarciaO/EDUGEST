"""
Restricción de asignaturas habilitadas.

La versión actual del aplicativo atiende solo Lengua y Literatura y Matemática. Otras
asignaturas (Ciencias Naturales, Inglés, Estudios Sociales...) pueden existir en la base de
datos, pero el aplicativo no las muestra ni permite usarlas. Se configura en el archivo .env
con `ASIGNATURAS_HABILITADAS` (nombres separados por coma); si se deja vacío, se habilitan
todas. Para cambiarlo no hace falta tocar el código ni migrar la base de datos.

La comparación de nombres no distingue mayúsculas, tildes ni espacios repetidos.
"""

import unicodedata

from django.conf import settings


def _normalizar(nombre):
    sin_tildes = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.casefold().split())


def nombres_habilitados():
    return list(settings.ASIGNATURAS_HABILITADAS)


def restringe():
    """False si la configuración está vacía (todas las asignaturas habilitadas)."""
    return bool(nombres_habilitados())


def nombre_habilitado(nombre):
    if not restringe():
        return True
    return _normalizar(nombre) in {_normalizar(n) for n in nombres_habilitados()}


def asignatura_habilitada(asignatura):
    return nombre_habilitado(asignatura.nombre)


def ids_habilitados():
    """Ids de las asignaturas habilitadas (la tabla es pequeña: se filtra en Python)."""
    from .models import Asignatura

    return [a.id for a in Asignatura.objects.only("id", "nombre") if nombre_habilitado(a.nombre)]


def asignaturas_habilitadas():
    from .models import Asignatura

    if not restringe():
        return Asignatura.objects.all()
    return Asignatura.objects.filter(id__in=ids_habilitados())


def solo_habilitadas(qs, campo="asignatura_id"):
    """Filtra un queryset por la asignatura indicada en `campo` (p. ej. 'tema__asignatura_id')."""
    if not restringe():
        return qs
    return qs.filter(**{f"{campo}__in": ids_habilitados()})


def exigir_habilitada(asignatura):
    """Para los `validate_*` de los serializers: rechaza una asignatura no habilitada."""
    from rest_framework import serializers

    if not asignatura_habilitada(asignatura):
        raise serializers.ValidationError(mensaje_asignatura_no_habilitada())
    return asignatura


def mensaje_asignatura_no_habilitada():
    return (
        f"Por ahora el aplicativo solo está habilitado para {' y '.join(nombres_habilitados())}. "
        "Esta asignatura aún no está disponible."
    )
