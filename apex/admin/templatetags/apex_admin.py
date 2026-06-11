"""Templatetags for the Apex admin theme.

``apex_admin_dashboard_cards`` walks ``admin.site._registry``, picks the
``ModelAdmin`` classes that opted in via ``show_in_dashboard = True``, and
returns a list of cards ready for the themed index template. Counts use the
model's default manager so soft-delete managers (Apex's pattern) hide archived
rows — matching what staff see in the changelist.
"""

from __future__ import annotations

from django import template
from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext as _

register = template.Library()


@register.simple_tag(takes_context=True)
def apex_admin_dashboard_cards(context):
    """Return a list of dicts: ``{label, count, icon, changelist_url, add_url}``.

    Only includes models whose ``ModelAdmin`` exposes ``show_in_dashboard =
    True`` (the ``apex.admin.ModelAdmin`` mixin) AND that the current user has
    view permission on. Silently skips models whose count query fails (e.g.
    backing table not migrated yet).
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    cards = []

    for model, model_admin in admin.site._registry.items():
        if not getattr(model_admin, "show_in_dashboard", False):
            continue
        if user is not None and not model_admin.has_view_permission(request):
            continue

        try:
            count = model._default_manager.count()
        except Exception:
            continue

        opts = model._meta
        try:
            changelist_url = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_changelist"
            )
        except NoReverseMatch:
            changelist_url = None
        try:
            add_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
        except NoReverseMatch:
            add_url = None

        cards.append(
            {
                "label": opts.verbose_name_plural.title(),
                "count": count,
                "icon": getattr(model_admin, "apex_icon", "box"),
                "changelist_url": changelist_url,
                "add_url": add_url,
                "app_label": opts.app_label,
                "model_name": opts.model_name,
            }
        )

    cards.sort(key=lambda c: c["label"])
    return cards


@register.simple_tag
def apex_admin_model_icon(app_label, model_name):
    """Return the Lucide icon name for a registered model, or 'box' fallback.

    Used by app_index.html to give each model in an app a visual anchor —
    the icon comes from ``ModelAdmin.apex_icon`` so app authors can pick.
    """
    for model, model_admin in admin.site._registry.items():
        opts = model._meta
        if opts.app_label == app_label and opts.model_name == model_name:
            return getattr(model_admin, "apex_icon", "box")
    return "box"


@register.simple_tag
def apex_admin_total_models():
    """Total registered admin models — shown next to 'Models' header on /admin/."""
    return len(admin.site._registry)


@register.simple_tag
def apex_admin_label_apps(label):
    """Translatable wrapper so the template can stay text-only."""
    return _(label)
