from django.apps import AppConfig


class ApexAdminConfig(AppConfig):
    """Apex admin theme app.

    Needs to live in ``INSTALLED_APPS`` (above ``django.contrib.admin``) so the
    template loader picks up our ``templates/admin/`` overrides and the
    ``apex_admin`` templatetag library is registered.
    """

    name = "apex.admin"
    label = "apex_admin"
    verbose_name = "Apex admin theme"
