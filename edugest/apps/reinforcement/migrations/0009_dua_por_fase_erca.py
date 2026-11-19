"""
DUA dentro de cada fase del ciclo ERCA: un apoyo para Experiencia, Reflexión,
Conceptualización y Aplicación en cada tema del plan.

Agrega los cuatro campos y los prellena con las reglas del sistema en los temas que ya
existían (sin tocar los tres principios generales ni el origen del DUA).
"""

from django.db import migrations, models


def prellenar(apps, schema_editor):
    from apps.reinforcement import dua

    TemaPlan = apps.get_model("reinforcement", "TemaPlan")
    campos = [f"dua_{fase}" for fase in dua.FASES]
    for tema_plan in TemaPlan.objects.select_related("plan__asignatura", "tema", "dificultad"):
        if any(getattr(tema_plan, c) for c in campos):
            continue
        sugerido = dua.sugerir_fases(
            tema_plan.plan.asignatura.nombre, tema_plan.tema.nombre, tema_plan.nivel_dificultad,
            # En las migraciones no existen las propiedades del modelo: se usa el campo real.
            reincidente=bool(tema_plan.dificultad and tema_plan.dificultad.veces_detectada > 1),
            motivo=tema_plan.motivo,
        )
        for fase in dua.FASES:
            setattr(tema_plan, f"dua_{fase}", sugerido[fase])
        tema_plan.save(update_fields=campos)


class Migration(migrations.Migration):
    dependencies = [("reinforcement", "0008_completar_erca_y_dua")]

    operations = [
        migrations.AddField(
            model_name="temaplan",
            name="dua_experiencia",
            field=models.TextField(blank=True, verbose_name="DUA en la fase de Experiencia"),
        ),
        migrations.AddField(
            model_name="temaplan",
            name="dua_reflexion",
            field=models.TextField(blank=True, verbose_name="DUA en la fase de Reflexión"),
        ),
        migrations.AddField(
            model_name="temaplan",
            name="dua_conceptualizacion",
            field=models.TextField(blank=True, verbose_name="DUA en la fase de Conceptualización"),
        ),
        migrations.AddField(
            model_name="temaplan",
            name="dua_aplicacion",
            field=models.TextField(blank=True, verbose_name="DUA en la fase de Aplicación"),
        ),
        migrations.RunPython(prellenar, migrations.RunPython.noop),
    ]
