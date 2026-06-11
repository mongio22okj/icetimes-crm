"""Apex-themed Django admin.

Drop-in replacement for ``django.contrib.admin``'s ``ModelAdmin`` that ships
with the Apex visual theme. Templates live in ``templates/admin/`` and
override Django's defaults via the project template loader, so any admin
registered with the stock ``admin.ModelAdmin`` also picks up the theme — the
``apex.admin.ModelAdmin`` base class is the recommended hook for future
conveniences (sections, tabs, compressed fields, dashboard cards).

Usage::

    from django.contrib import admin
    from apex.admin import ModelAdmin

    @admin.register(MyModel)
    class MyModelAdmin(ModelAdmin):
        list_display = ("name", "created_at")
        show_in_dashboard = True   # surfaces a stat card on /admin/
"""

from apex.admin.base import ModelAdmin, StackedInline, TabularInline

__all__ = ["ModelAdmin", "StackedInline", "TabularInline"]

default_app_config = "apex.admin.apps.ApexAdminConfig"
