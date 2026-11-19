"""
Destinatarios de las evaluaciones de refuerzo que ya existían.

El campo lo crea 0005_actividad_destinatarios; esta migración lo llena para las
evaluaciones de refuerzo anteriores con:
- los estudiantes que ya tienen nota en ella (para no esconder notas ya registradas), y
- los que hoy tienen un plan de la asignatura completado y pendiente de evaluación.
Las actividades normales no cambian (siguen siendo para todo el paralelo).
"""

from django.db import migrations


def asignar_destinatarios(apps, schema_editor):
    Actividad = apps.get_model("activities", "Actividad")
    Calificacion = apps.get_model("grades", "Calificacion")
    Estudiante = apps.get_model("academic", "Estudiante")

    for actividad in Actividad.objects.filter(es_evaluacion_refuerzo=True).select_related("asignacion"):
        calificados = set(
            Calificacion.objects.filter(actividad=actividad).values_list("estudiante_id", flat=True)
        )
        pendientes = set(
            Estudiante.objects.filter(
                paralelo_id=actividad.asignacion.paralelo_id,
                is_active=True,
                planes_refuerzo__asignatura_id=actividad.asignacion.asignatura_id,
                planes_refuerzo__estado="COMPLETADA",
                planes_refuerzo__temas__superado__isnull=True,
            ).values_list("id", flat=True)
        )
        actividad.destinatarios.add(*(calificados | pendientes))


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0005_actividad_destinatarios"),
        ("grades", "0001_initial"),
        ("reinforcement", "0010_prellenar_dua_por_fase"),
    ]

    operations = [migrations.RunPython(asignar_destinatarios, migrations.RunPython.noop)]