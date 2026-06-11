from django.apps import AppConfig


class ActivityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.activity"

    def ready(self):
        # Register signal handlers — they call record() to persist events.
        from . import signals  # noqa: F401
