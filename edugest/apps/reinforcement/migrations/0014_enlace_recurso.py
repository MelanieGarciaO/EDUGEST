"""
Enlace opcional del recurso (video, audio o recurso digital en internet, solo https).
Se agrega al recurso del banco y a la actividad del plan, donde se copia del recurso.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reinforcement", "0013_evidencias_audio_texto")]

    operations = [
        migrations.AddField(
            model_name="recursorefuerzo",
            name="enlace",
            field=models.URLField(blank=True, max_length=500, verbose_name="enlace del recurso"),
        ),
        migrations.AddField(
            model_name="actividadrefuerzo",
            name="enlace",
            field=models.URLField(blank=True, max_length=500, verbose_name="enlace del recurso"),
        ),
    ]