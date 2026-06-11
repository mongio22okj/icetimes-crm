from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        # Register the auth-event signal handlers (login / logout /
        # login_failed → AuditEvent rows). Import side-effect: the
        # @receiver decorators wire themselves on import.
        from apps.accounts import signals  # noqa: F401
