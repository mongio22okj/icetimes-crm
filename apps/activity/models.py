"""Global activity event stream.

Distinct from apps.notifications (which is a per-recipient inbox). This
model is a flat, append-only log of "who did what" — used for the global
activity timeline page and admin audit-trail surfaces.

Event categories drive a colored icon in the timeline UI; verbs are
human-readable strings like "created" or "completed".
"""
from django.conf import settings
from django.db import models


class ActivityEvent(models.Model):
    CATEGORY = [
        ("auth",     "Auth"),         # login / logout
        ("customer", "Customer"),
        ("order",    "Order"),
        ("invoice",  "Invoice"),
        ("project",  "Project"),
        ("task",     "Task"),
        ("system",   "System"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="activity_events", null=True, blank=True,
    )
    category = models.CharField(max_length=16, choices=CATEGORY, default="system")
    verb = models.CharField(max_length=64)             # e.g. "created", "completed"
    label = models.CharField(max_length=300)           # e.g. "Order ORD-00042"
    url = models.CharField(max_length=300, blank=True) # link target for the row
    icon = models.CharField(max_length=32, blank=True) # apex icon name; UI default by category
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self) -> str:
        who = self.actor.username if self.actor else "system"
        return f"{who} {self.verb} {self.label}"

    @property
    def default_icon(self) -> str:
        if self.icon:
            return self.icon
        return {
            "auth": "user",
            "customer": "user-plus",
            "order": "shopping-cart",
            "invoice": "file-text",
            "project": "briefcase",
            "task": "check",
            "system": "activity",
        }.get(self.category, "activity")
