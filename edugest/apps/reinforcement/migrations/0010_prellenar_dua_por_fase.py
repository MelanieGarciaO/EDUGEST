"""
Prellena el apoyo DUA de cada fase ERCA (Experiencia, Reflexión, Conceptualización,
Aplicación) en los temas de planes que ya existían.

Los campos los crea la migración 0009_temaplan_dua_aplicacion_and_more; esta solo les da
contenido con las reglas del sistema. No toca los tres principios generales ni el origen
del DUA, ni los temas que ya tienen algún apoyo por fase.
"""

from django.db import migrations


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
    dependencies = [("reinforcement", "0009_temaplan_dua_aplicacion_and_more")]

    operations = [migrations.RunPython(prellenar, migrations.RunPython.noop)]
