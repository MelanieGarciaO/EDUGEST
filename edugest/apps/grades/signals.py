"""
Eventos del módulo de calificaciones. Se envían después de confirmar la transacción
(transaction.on_commit) y reciben el argumento `dificultad`.

- dificultad_detectada: se detectó una dificultad nueva o se reabrió una ya superada.
- dificultad_superada: el promedio del estudiante en el tema volvió a 7,00 o más.
- calificaciones_guardadas: se crearon o corrigieron notas de una actividad (síncrona).

El módulo de refuerzo y el de notificaciones pueden suscribirse sin que `grades`
dependa de ellos.
"""

from django.dispatch import Signal

dificultad_detectada = Signal()
dificultad_superada = Signal()

# Se envía DENTRO de la transacción del guardado (no en on_commit), para que quien escuche
# (el módulo de refuerzo, al registrar evaluaciones) quede en la misma operación atómica.
# Argumentos: actividad, estudiantes (ids con notas creadas o corregidas).
calificaciones_guardadas = Signal()
