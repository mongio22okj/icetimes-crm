from django.apps import AppConfig


class DocsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.docs"
    label = "apex_docs"  # avoid clashing with Django's bundled "docs" app name
