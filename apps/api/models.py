"""API tokens + webhook subscriptions.

APIKey storage:
- We store SHA-256(key) — the raw key is shown to the user exactly once
  on creation, and never retrievable again. This matches Stripe / GitHub
  conventions and means a database leak doesn't leak usable keys.
- `prefix` (first 8 chars of the raw key, after a brand prefix like
  "apex_") is stored in cleartext so the UI can show a non-secret
  identifier for each key.

Webhook delivery:
- `Webhook.events` is a comma-joined list of event names ("invoice.paid",
  "customer.created", etc.). Subscribers match if `event in events`.
- Outbound HTTP POSTs are signed with HMAC-SHA256 of the secret over
  the raw JSON body, sent in the `X-Apex-Signature` header.
- `WebhookDelivery` rows are created for every send attempt — successful
  or not — so the UI can surface a delivery log.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

KEY_BRAND = "apex"           # prefix on every raw key, e.g. "apex_..."
KEY_RANDOM_BYTES = 32        # 256 bits of entropy
KEY_PREFIX_LENGTH = 8        # how many chars of the random suffix we keep


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class APIKey(models.Model):
    """Per-user API token. The raw key is never stored — only its hash.

    `key_prefix` is the first KEY_PREFIX_LENGTH chars of the random
    suffix so the user can identify their keys without secrets.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=80, help_text="User-supplied label, e.g. 'Production server'.")
    key_prefix = models.CharField(max_length=16)         # non-secret display value
    key_hash = models.CharField(max_length=128, db_index=True)  # SHA-256 hex
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "revoked_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.name} ({self.key_prefix}…)"

    @classmethod
    def generate(cls, user, name: str, expires_at=None) -> tuple[APIKey, str]:
        """Create an APIKey and return (instance, raw_key).

        `raw_key` is `apex_<random>` — show it once, then discard.
        """
        random_part = secrets.token_urlsafe(KEY_RANDOM_BYTES).rstrip("=")
        raw = f"{KEY_BRAND}_{random_part}"
        instance = cls.objects.create(
            user=user,
            name=name,
            key_prefix=random_part[:KEY_PREFIX_LENGTH],
            key_hash=_hash_key(raw),
            expires_at=expires_at,
        )
        return instance, raw

    @classmethod
    def lookup(cls, raw: str) -> APIKey | None:
        """Find a non-revoked, non-expired APIKey matching the raw value."""
        if not raw or "_" not in raw:
            return None
        try:
            obj = cls.objects.get(key_hash=_hash_key(raw))
        except cls.DoesNotExist:
            return None
        if obj.revoked_at is not None:
            return None
        if obj.expires_at is not None and obj.expires_at < timezone.now():
            return None
        return obj

    def revoke(self) -> None:
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def touch(self) -> None:
        """Bump last_used_at — called by the auth backend on every request."""
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < timezone.now():
            return False
        return True


class Webhook(models.Model):
    """Outbound webhook subscription.

    Owned by a single user; the user receives signed POSTs at `url` for
    every event whose name appears in `events`. `secret` is shared
    between Apex and the subscriber's receiving server for signature
    verification — generated server-side on creation.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhooks",
    )
    name = models.CharField(max_length=80, blank=True)
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=64)
    events = models.CharField(
        max_length=500,
        help_text="Comma-separated event names: 'invoice.paid,customer.created'.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_active"])]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.url}"

    @classmethod
    def generate_secret(cls) -> str:
        return secrets.token_urlsafe(32).rstrip("=")

    def event_set(self) -> set[str]:
        return {e.strip() for e in (self.events or "").split(",") if e.strip()}

    def matches(self, event: str) -> bool:
        return event in self.event_set()

    def sign(self, body: bytes) -> str:
        return hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class WebhookDelivery(models.Model):
    """Audit log of webhook send attempts (success or failure)."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed",  "Failed"),
    ]

    webhook = models.ForeignKey(
        Webhook, on_delete=models.CASCADE, related_name="deliveries",
    )
    event = models.CharField(max_length=80)
    payload = models.JSONField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    response_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} → {self.webhook_id} [{self.status}]"


def serialize_event_payload(event: str, data: dict) -> bytes:
    """Canonical JSON encoding for webhook signing.

    Sorted keys + no whitespace so signatures are reproducible across
    Python versions.
    """
    return json.dumps(
        {"event": event, "data": data, "ts": int(timezone.now().timestamp())},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
