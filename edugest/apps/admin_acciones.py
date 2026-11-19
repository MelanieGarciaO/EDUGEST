"""
Acciones del admin de Django para cambiar el estado de varios registros a la vez.

Regla general: el admin aplica LAS MISMAS reglas que la app (no es una puerta trasera).
- Registros con «Activo» (is_active): Activar / Desactivar seleccionados. Si el serializer
  de la app valida la desactivación (p. ej. «no puedes desactivar un paralelo con
  estudiantes activos»), esa regla se respeta y el registro se omite con su motivo.
- Cada admin puede ajustar qué pasa al cambiar (p. ej. al desactivar un usuario se cierran
  sus sesiones).

Los estados que el sistema calcula solo (dificultades, plan completado o evaluado,
notificaciones) no tienen acciones: se cambian desde sus pantallas o se recalculan.
"""

from django.contrib import admin, messages
from rest_framework.exceptions import ValidationError


def primer_error(exc):
    """Mensaje legible de una ValidationError de DRF (dict, lista o texto)."""
    detalle = getattr(exc, "detail", exc)
    while isinstance(detalle, (dict, list)) and detalle:
        detalle = next(iter(detalle.values())) if isinstance(detalle, dict) else detalle[0]
    return str(detalle)


def informar(modelo_admin, request, hechos, omitidos, accion):
    """Mensajes de resultado: cuántos cambiaron y por qué se omitió cada uno."""
    if hechos:
        modelo_admin.message_user(request, f"Listo — {accion}: {hechos}.", messages.SUCCESS)
    for texto in omitidos[:10]:
        modelo_admin.message_user(request, f"Sin cambios — {texto}", messages.WARNING)
    if len(omitidos) > 10:
        modelo_admin.message_user(request, f"…y {len(omitidos) - 10} más sin cambios.", messages.WARNING)
    if not hechos and not omitidos:
        modelo_admin.message_user(request, "Los registros seleccionados ya estaban así.", messages.INFO)


class AccionesActivoMixin:
    """Agrega «Activar» y «Desactivar seleccionados» a un ModelAdmin con campo is_active."""

    # Serializer de la app cuyo validate_is_active tiene las reglas de negocio (opcional).
    serializer_activo = None

    def get_actions(self, request):
        acciones = super().get_actions(request)
        for nombre in ("activar_seleccionados", "desactivar_seleccionados"):
            funcion = getattr(type(self), nombre)
            acciones[nombre] = (funcion, nombre, funcion.short_description)
        return acciones

    def validar_activo(self, request, obj, valor):
        """Lanza ValidationError si la app no permitiría el cambio."""
        validador = getattr(self.serializer_activo, "validate_is_active", None)
        if validador is not None:
            validador(self.serializer_activo(instance=obj), valor)

    def aplicar_activo(self, request, obj, valor):
        obj.is_active = valor
        campos = ["is_active"] + (["updated_at"] if hasattr(obj, "updated_at") else [])
        obj.save(update_fields=campos)

    def _cambiar_activo(self, request, queryset, valor):
        hechos, omitidos = 0, []
        for obj in queryset.exclude(is_active=valor):
            try:
                self.validar_activo(request, obj, valor)
            except ValidationError as exc:
                omitidos.append(f"{obj}: {primer_error(exc)}")
                continue
            self.aplicar_activo(request, obj, valor)
            hechos += 1
        informar(self, request, hechos, omitidos, "activados" if valor else "desactivados")

    @admin.action(description="Activar seleccionados")
    def activar_seleccionados(self, request, queryset):
        self._cambiar_activo(request, queryset, True)

    @admin.action(description="Desactivar seleccionados")
    def desactivar_seleccionados(self, request, queryset):
        self._cambiar_activo(request, queryset, False)
