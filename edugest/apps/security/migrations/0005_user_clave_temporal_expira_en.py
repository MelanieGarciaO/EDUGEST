"""
Vencimiento de la contraseña temporal de bienvenida (2 horas).

La columna «clave_temporal_expira_en» ya la crea la migración 0004; esta solo da un plazo
de 2 horas, desde ahora, a las cuentas que ya estaban pendientes de activar.
"""

from datetime import timedelta

from django.db import migrations
from django.utils import timezone


def plazo_para_pendientes(apps, schema_editor):
    User = apps.get_model("security", "User")
    User.objects.filter(must_change_password=True, last_login__isnull=True).update(
        clave_temporal_expira_en=timezone.now() + timedelta(hours=2)
    )


class Migration(migrations.Migration):
    dependencies = [("security", "0004_codigorecuperacion_tipo_and_more")]

    operations = [
        migrations.RunPython(plazo_para_pendientes, migrations.RunPython.noop),
    ]
