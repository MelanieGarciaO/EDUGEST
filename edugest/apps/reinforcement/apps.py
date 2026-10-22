from django.apps import AppConfig


class ReinforcementConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reinforcement"
    label = "reinforcement"
    verbose_name = "Refuerzo académico"

    def ready(self):
        from . import receivers  # noqa: F401
