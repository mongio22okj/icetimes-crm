"""Apex ``ModelAdmin`` base class.

Thin wrapper over Django's ``admin.ModelAdmin``. Provides three Apex-specific
knobs: ``show_in_dashboard`` (surface a stat card on /admin/), ``apex_icon``
(Lucide icon name for cards + app-index list), and ``hide_readonly_on_add``
(skip rendering readonly fields on add forms where they'd be empty
placeholders). Future niceties (tabs, sections, compressed fieldsets) attach
here so admins opting into them don't pay for what they don't use.
"""

from __future__ import annotations

from django.contrib import admin


class ApexAdminMixin:
    """Shared behaviour for ``ModelAdmin``, ``StackedInline``, ``TabularInline``."""

    #: When True, the model appears as a stat card on the themed admin index.
    #: Counts run through ``Model._default_manager.count()`` — cheap on indexed
    #: PKs, but opt in deliberately on huge tables.
    show_in_dashboard: bool = False

    #: Optional Lucide icon name (see ``apps/core/templatetags/apex.py:ICONS``)
    #: shown on the dashboard card and app-index list. Falls back to ``box``.
    apex_icon: str = "box"

    #: When True (default), readonly fields are dropped from add forms — they
    #: render as "-" placeholders otherwise, since the row doesn't exist yet
    #: and there's nothing to display. Set to False on admins that need to
    #: show computed/default values pre-save (e.g. an auto-generated
    #: reference number derived from form data).
    hide_readonly_on_add: bool = True

    def get_readonly_fields(self, request, obj=None):
        """Hide readonly fields on add forms when ``hide_readonly_on_add``."""
        if obj is None and self.hide_readonly_on_add:
            return ()
        return super().get_readonly_fields(request, obj)


class ModelAdmin(ApexAdminMixin, admin.ModelAdmin):
    pass


class StackedInline(ApexAdminMixin, admin.StackedInline):
    pass


class TabularInline(ApexAdminMixin, admin.TabularInline):
    pass
