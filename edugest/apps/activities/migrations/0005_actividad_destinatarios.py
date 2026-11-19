"""
Evaluaciones de refuerzo dirigidas solo a los estudiantes que completaron su plan.

Agrega «destinatarios» a la actividad. Para las evaluaciones de refuerzo que ya existían se
llenan con los estudiantes que ya tienen nota en ella y con los que hoy tienen un plan de la
asignatura completado y pendiente de evaluación. Las actividades normales no cambian.
"""

from django.db import migrations, models


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
        actividad.destinatarios.set(calificados | pendientes)


class Migration(migrations.Migration):
    dependencies = [
        ("activities", "0004_actividad_modalidad_entrega_adjuntoactividad_and_more"),
        ("academic", "0001_initial"),
        ("grades", "0001_initial"),
        ("reinforcement", "0010_prellenar_dua_por_fase"),
    ]

    operations = [
        migrations.AddField(
            model_name="actividad",
            name="destinatarios",
            field=models.ManyToManyField(
                blank=True,
                related_name="evaluaciones_refuerzo",
                to="academic.estudiante",
                verbose_name="dirigida a",
            ),
        ),
        migrations.RunPython(asignar_destinatarios, migrations.RunPython.noop),
    ]
