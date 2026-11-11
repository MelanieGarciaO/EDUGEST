from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notificaciones"

    def ready(self):
        from . import receivers  # noqa: F401  (suscribe los avisos a las señales de negocio)
