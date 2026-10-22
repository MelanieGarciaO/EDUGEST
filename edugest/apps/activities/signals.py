"""
Eventos que emite el módulo de actividades. El módulo `notifications` se suscribe a
estas señales para avisar a los representantes; así `activities` no depende de él.

Todas se envían después de confirmar la transacción (transaction.on_commit) y reciben
el argumento `actividad`. `actividad_modificada` recibe además `campos`, la lista de
campos que cambiaron.

Ejemplo de suscripción:

    from django.dispatch import receiver
    from apps.activities.signals import actividad_publicada

    @receiver(actividad_publicada)
    def avisar(sender, actividad, **kwargs):
        ...
"""

from django.dispatch import Signal

actividad_publicada = Signal()
actividad_modificada = Signal()
actividad_cancelada = Signal()
