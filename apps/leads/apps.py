from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.leads"

    def ready(self):
        from . import signals  # noqa: F401  — registra il post_save su Lead
