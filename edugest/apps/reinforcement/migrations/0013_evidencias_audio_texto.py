"""
Evidencias en varias formas (DUA · acción y expresión): además de foto, audio y texto.
Las evidencias que ya existían son fotos JPEG.
"""

import apps.reinforcement.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reinforcement", "0012_deducir_formatos")]

    operations = [
        migrations.AddField(
            model_name="evidenciaactividad",
            name="tipo",
            field=models.CharField(
                choices=[("FOTO", "Foto"), ("AUDIO", "Audio"), ("TEXTO", "Texto")], default="FOTO", max_length=5
            ),
        ),
        migrations.AddField(
            model_name="evidenciaactividad",
            name="tipo_contenido",
            field=models.CharField(blank=True, default="image/jpeg", max_length=40, verbose_name="tipo de contenido"),
        ),
        migrations.AddField(
            model_name="evidenciaactividad",
            name="texto",
            field=models.TextField(blank=True, verbose_name="texto"),
        ),
        migrations.AlterField(
            model_name="evidenciaactividad",
            name="archivo",
            field=models.FileField(
                blank=True,
                max_length=255,
                storage=apps.reinforcement.models._almacen_evidencias,
                upload_to=apps.reinforcement.models._ruta_evidencia,
            ),
        ),
        migrations.AlterField(
            model_name="evidenciaactividad",
            name="tamano",
            field=models.PositiveIntegerField(default=0, help_text="Bytes del archivo guardado."),
        ),
    ]