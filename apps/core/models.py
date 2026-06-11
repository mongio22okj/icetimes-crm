"""Cross-cutting models that don't belong to any single feature app.

Currently:
- UserPreference: generic key/value JSON store (e.g. table column
  visibility — see apps.core.tables.prefs).
- SavedView: per-user saved filter+sort combos for the datatable.
"""
from django.conf import settings
from django.db import models


class UserPreference(models.Model):
    """Generic per-user JSON-blob preference store, addressed by string key.

    Keys are dotted to allow loose namespacing without a schema (e.g.
    "table.customers.visible_columns", "ui.density"). Helpers in
    apps.core.tables.prefs wrap reads/writes for table-related prefs.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    key = models.CharField(max_length=128)
    value = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"],
                name="uniq_userpreference_per_user_per_key",
            ),
        ]
        indexes = [models.Index(fields=["user", "key"])]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.key}"


class SavedView(models.Model):
    """A named filter+sort combo for a specific datatable, scoped to one user.

    `table_key` matches `TableConfig.key` (e.g. "customers"). `params`
    stores the URL query params (filters, sort, search) so applying the
    view is just a redirect with those params.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_views",
    )
    table_key = models.CharField(max_length=64)
    name = models.CharField(max_length=80)
    params = models.JSONField(default=dict, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["table_key", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "table_key", "name"],
                name="uniq_savedview_per_table_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "table_key"]),
            models.Index(fields=["user", "table_key", "is_default"]),
        ]

    def __str__(self) -> str:
        return f"{self.table_key} · {self.name}"
