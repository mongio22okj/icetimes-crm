from django.apps import AppConfig


class HelpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.help"
    label = "help_center"  # avoid clashing with Django's reserved 'help' label
