"""
Eventos del módulo de refuerzo. Se envían después de confirmar la transacción
(transaction.on_commit). El módulo `notifications` se suscribe a ellos.

- plan_aprobado(plan): el docente aprobó el plan; el representante ya puede verlo.
- plan_cancelado(plan): se canceló un plan (si había sido aprobado, la familia debe saberlo).
- actividad_refuerzo_cumplida(actividad, plan, cumplida_por): se marcó una actividad.
- plan_completado(plan): todas las actividades del plan quedaron cumplidas.
- plan_evaluado(plan): todos los temas del plan completado tienen nota de evaluación.
"""

from django.dispatch import Signal

plan_aprobado = Signal()
plan_cancelado = Signal()
actividad_refuerzo_cumplida = Signal()
plan_completado = Signal()
plan_evaluado = Signal()
