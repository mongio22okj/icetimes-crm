"""In-app notifications + per-user preferences + browser-push subscriptions.

Phase 13 expands the Phase 4c base:

- `Notification` gains a `category` (system / billing / mention / comment
  / security) plus an optional `actor` FK so list rows can render "Sara
  marked invoice INV-001 paid" with avatars. The original `kind` enum
  stays for back-compat — `category` is the new dimension that
  preferences key off.
- `NotificationPreference` — per-user × per-category × per-channel
  toggle. Channels are in_app / email / push. Lazy-defaulted via
  helpers so users don't need a row per category to receive defaults.
- `PushSubscription` — Web Push subscription endpoint for the optional
  browser-push channel. Real send via pywebpush (deferred); the model
  is here from the start so migrations don't churn later.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True, archived_at__isnull=True)

    def read(self):
        return self.filter(read_at__isnull=False, archived_at__isnull=True)

    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)

    def for_category(self, category):
        return self.filter(category=category) if category else self


CATEGORY_CHOICES = [
    ("system",   "System"),
    ("billing",  "Billing"),
    ("mention",  "Mention"),
    ("comment",  "Comment"),
    ("security", "Security"),
]
CATEGORY_DEFAULT = "system"

# Maps the Phase 4c `kind` enum to the new Phase 13 categories. Used
# during migration back-fill and as a fallback in the dispatch layer.
KIND_TO_CATEGORY = {
    "invoice_sent": "billing",
    "invoice_paid": "billing",
    "invoice_void": "billing",
    "order_placed": "system",
    "new_mail":     "mention",
    "new_chat":     "mention",
}

CHANNELS = ("in_app", "email", "push")
# Default channel state when the user hasn't customized this category.
# in_app on for everything; email on for billing + security only;
# push off everywhere (must be explicitly enabled with a subscription).
CHANNEL_DEFAULTS = {
    "system":   {"in_app": True,  "email": False, "push": False},
    "billing":  {"in_app": True,  "email": True,  "push": False},
    "mention":  {"in_app": True,  "email": False, "push": False},
    "comment":  {"in_app": True,  "email": False, "push": False},
    "security": {"in_app": True,  "email": True,  "push": False},
}


class Notification(models.Model):
    KIND_CHOICES = [
        ("invoice_sent", "Invoice sent"),
        ("invoice_paid", "Invoice paid"),
        ("invoice_void", "Invoice voided"),
        ("order_placed", "Order placed"),
        ("new_mail", "New mail"),
        ("new_chat", "New chat message"),
        ("mention", "Mention"),
        ("comment", "Comment"),
        ("security", "Security"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="actor_notifications",
        null=True, blank=True,
        help_text="The user that performed the action — for 'Sara mentioned you' rows.",
    )
    category = models.CharField(
        max_length=16, choices=CATEGORY_CHOICES, default=CATEGORY_DEFAULT,
        help_text="Drives preference matching + filter pills on the list page.",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "archived_at"]),
            models.Index(fields=["recipient", "category", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    def archive(self) -> None:
        if self.archived_at is None:
            self.archived_at = timezone.now()
            # Archiving implies read.
            if self.read_at is None:
                self.read_at = self.archived_at
                self.save(update_fields=["archived_at", "read_at"])
            else:
                self.save(update_fields=["archived_at"])

    @property
    def is_unread(self) -> bool:
        return self.read_at is None

    @property
    def target_url(self) -> str:
        """Phase 13 alias for `url`. New code should prefer `target_url`."""
        return self.url


class NotificationPreference(models.Model):
    """Per-user × per-category channel toggles.

    Rows are lazily created when a user explicitly customizes a category;
    fetch the effective state with `get_effective_pref(user, category,
    channel)` which falls back to `CHANNEL_DEFAULTS` for missing rows.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES)
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)
    push = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category"],
                name="uniq_notificationpreference_per_user_per_category",
            ),
        ]
        indexes = [models.Index(fields=["user", "category"])]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.category}"


def get_effective_pref(user, category: str, channel: str) -> bool:
    """Resolve whether a user wants notifications of (category, channel).

    Falls back to `CHANNEL_DEFAULTS` when the user hasn't customized.
    Anonymous / unauthenticated users always get False.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if channel not in CHANNELS:
        return False
    try:
        pref = NotificationPreference.objects.get(user=user, category=category)
    except NotificationPreference.DoesNotExist:
        return CHANNEL_DEFAULTS.get(category, {}).get(channel, False)
    return getattr(pref, channel, False)


class PushSubscription(models.Model):
    """A Web Push subscription registered by a browser.

    Created via the `/notifications/push/subscribe/` endpoint; deleted
    via `/notifications/push/unsubscribe/`. Real send via pywebpush
    is deferred — model lives here so the schema is stable.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=64)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user"])]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.endpoint[:40]}…"
