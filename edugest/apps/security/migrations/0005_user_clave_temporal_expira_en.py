"""
Vencimiento de la contraseña temporal de bienvenida (2 horas).
Las cuentas que ya estaban pendientes de activar reciben un plazo de 2 horas desde ahora.
"""

from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def plazo_para_pendientes(apps, schema_editor):
    User = apps.get_model("security", "User")
    User.objects.filter(must_change_password=True, last_login__isnull=True).update(
        clave_temporal_expira_en=timezone.now() + timedelta(hours=2)
    )


class Migration(migrations.Migration):
    dependencies = [("security", "0004_codigorecuperacion_tipo_and_more")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="clave_temporal_expira_en",
            field=models.DateTimeField(blank=True, null=True, verbose_name="la clave temporal vence el"),
        ),
        migrations.RunPython(plazo_para_pendientes, migrations.RunPython.noop),
    ]