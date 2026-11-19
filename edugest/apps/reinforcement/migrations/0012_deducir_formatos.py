"""
Deduce los formatos (DUA · representación) de los recursos y actividades de plan que ya
existían. Los campos los crea 0011_actividadrefuerzo_formatos_recursorefuerzo_formatos.
"""

from django.db import migrations


def deducir(apps, schema_editor):
    from apps.reinforcement.formatos import completar_existentes

    completar_existentes(
        apps.get_model("reinforcement", "RecursoRefuerzo"),
        apps.get_model("reinforcement", "ActividadRefuerzo"),
    )


class Migration(migrations.Migration):
    dependencies = [("reinforcement", "0011_actividadrefuerzo_formatos_recursorefuerzo_formatos")]

    operations = [migrations.RunPython(deducir, migrations.RunPython.noop)]