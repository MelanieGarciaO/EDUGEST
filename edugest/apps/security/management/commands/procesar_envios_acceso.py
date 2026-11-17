"""
Procesa la cola de envíos de contraseñas temporales (usuarios importados).

Normalmente la cola avanza sola en segundo plano. Este comando es el respaldo para
programarlo, por ejemplo cada 5 minutos, o para ejecutarlo a mano:
    python manage.py procesar_envios_acceso
"""

from django.core.management.base import BaseCommand

from apps.security import cola_accesos


class Command(BaseCommand):
    help = "Envía los correos de acceso pendientes de las importaciones de usuarios."

    def add_arguments(self, parser):
        parser.add_argument("--maximo", type=int, default=None, help="Máximo de correos a enviar en esta ejecución.")

    def handle(self, *args, maximo=None, **options):
        r = cola_accesos.procesar(maximo=maximo)
        self.stdout.write(self.style.SUCCESS(
            f"Enviados: {r['ok']} · Con error: {r['error']} · Reprogramados por límite del servicio: {r['cuota']} · "
            f"Omitidos: {r['omitido']}"
        ))
