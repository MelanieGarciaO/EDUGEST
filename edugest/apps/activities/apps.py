from django.apps import AppConfig


class ActivitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.activities"
    label = "activities"
    verbose_name = "Actividades"

    def ready(self):
        from . import checks  # noqa: F401  (registra la comprobación del modelo de spaCy)
