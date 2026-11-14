"""
Completa los planes que ya existían antes del DUA y del ciclo ERCA:
- Asigna una fase ERCA a cada actividad sin fase (mismas reglas que al generar un plan).
- Prellena los apoyos DUA de cada tema que no los tenga.
No agrega actividades guía a planes existentes (no se altera lo que la familia ya ve).
"""

from django.db import migrations


def completar(apps, schema_editor):
    from apps.reinforcement import dua, erca

    TemaPlan = apps.get_model("reinforcement", "TemaPlan")
    ActividadRefuerzo = apps.get_model("reinforcement", "ActividadRefuerzo")

    for tema_plan in TemaPlan.objects.select_related("plan__asignatura", "tema", "dificultad"):
        actividades = list(ActividadRefuerzo.objects.filter(tema_plan=tema_plan).order_by("orden", "id"))
        sin_fase = [a for a in actividades if not a.fase]
        if sin_fase:
            for actividad, fase in erca.asignar_fases(sin_fase):
                actividad.fase = fase
                actividad.save(update_fields=["fase"])

        if not (tema_plan.dua_implicacion or tema_plan.dua_representacion or tema_plan.dua_accion_expresion):
            sugerido = dua.sugerir(
                tema_plan.plan.asignatura.nombre, tema_plan.tema.nombre, tema_plan.nivel_dificultad,
                # En las migraciones no existen las propiedades del modelo: se usa el campo real.
                reincidente=bool(tema_plan.dificultad and tema_plan.dificultad.veces_detectada > 1),
                motivo=tema_plan.motivo,
            )
            tema_plan.dua_implicacion = sugerido["implicacion"]
            tema_plan.dua_representacion = sugerido["representacion"]
            tema_plan.dua_accion_expresion = sugerido["accion_expresion"]
            tema_plan.save(update_fields=["dua_implicacion", "dua_representacion", "dua_accion_expresion"])


class Migration(migrations.Migration):
    dependencies = [
        ("reinforcement", "0007_actividadrefuerzo_fase_recursorefuerzo_fase_and_more"),
        ("grades", "0002_dificultad_veces_detectada"),  # crea el campo veces_detectada que se usa aquí
    ]

    operations = [migrations.RunPython(completar, migrations.RunPython.noop)]