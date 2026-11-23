"""
Validaciones de texto compartidas por los formularios, las importaciones desde Excel y el
admin (todos pasan por los mismos serializers).
"""

import re
from rest_framework import serializers

# Una «palabra» de un nombre: solo letras de cualquier alfabeto (incluye tildes, ñ y ü),
# sin dígitos ni guion bajo. Entre palabras se admite un espacio, apóstrofe o guion:
# «María José», «O'Neil», «Pérez-Gil».
_NOMBRE_PERSONA = re.compile(r"^[^\W\d_]+(?:[ '’-][^\W\d_]+)*$")
_UNA_LETRA = re.compile(r"[^\W\d_]")
MIN_NOMBRE_PERSONA = 2


def nombre_persona(valor, campo="nombres"):
    """Normaliza los espacios y exige solo letras (2 o más). Devuelve el valor limpio."""
    limpio = " ".join((valor or "").split())
    if len(limpio) < MIN_NOMBRE_PERSONA:
        raise serializers.ValidationError(f"Escribe los {campo} completos (al menos {MIN_NOMBRE_PERSONA} letras).")
    if not _NOMBRE_PERSONA.match(limpio):
        raise serializers.ValidationError(
            f"Los {campo} solo pueden tener letras, espacios, apóstrofes o guiones (sin números ni símbolos)."
        )
    return limpio


class NombresPersonaFormMixin:
    """Misma regla de nombres en los formularios del admin de Django (no usan los serializers)."""

    def _nombre(self, campo, etiqueta):
        from django import forms

        try:
            return nombre_persona(self.cleaned_data.get(campo), etiqueta)
        except serializers.ValidationError as exc:
            raise forms.ValidationError(exc.detail[0]) from None

    def clean_first_name(self):
        return self._nombre("first_name", "nombres")

    def clean_last_name(self):
        return self._nombre("last_name", "apellidos")


def con_letras(valor, mensaje="Debe contener al menos una letra."):
    """Normaliza los espacios y exige al menos una letra (rechaza «123» o «#$»)."""
    limpio = " ".join((valor or "").split())
    if not _UNA_LETRA.search(limpio):
        raise serializers.ValidationError(mensaje)
    return limpio
