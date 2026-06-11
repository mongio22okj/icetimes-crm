from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("staff", "Staff"),
    ]
    email = models.EmailField(unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="staff")
    bio = models.TextField(blank=True)
    title = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)

    # Phase 17 — pending account deletion (soft delete with grace period).
    pending_deletion_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when the user requests deletion; cleared on cancel. "
                  "A management command performs hard delete after the grace period.",
    )

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_pending_deletion(self) -> bool:
        return self.pending_deletion_at is not None


class SessionMetadata(models.Model):
    """Sidecar for django.contrib.sessions.Session.

    Django's Session table stores serialized session data but no user
    or device info. We populate this model from middleware on every
    authenticated request so the Sessions settings pane can show
    "iPhone · 192.0.2.4 · last seen 2 minutes ago".
    """
    session_key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_metadata",
    )
    user_agent = models.CharField(max_length=400, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "-last_seen_at"])]

    def device_label(self) -> str:
        """Best-effort short label from the user agent.

        Just enough to disambiguate sessions in the UI — we don't ship a
        full UA parser.
        """
        ua = (self.user_agent or "").lower()
        platform = "Unknown device"
        for needle, label in (
            ("iphone", "iPhone"),
            ("ipad", "iPad"),
            ("android", "Android"),
            ("mac os", "Mac"),
            ("macintosh", "Mac"),
            ("windows", "Windows"),
            ("linux", "Linux"),
        ):
            if needle in ua:
                platform = label
                break
        browser = "browser"
        for needle, label in (
            ("edg/", "Edge"),
            ("chrome/", "Chrome"),
            ("firefox/", "Firefox"),
            ("safari/", "Safari"),
        ):
            if needle in ua:
                browser = label
                break
        return f"{platform} · {browser}"


class AuditEvent(models.Model):
    """Per-user security/lifecycle event log.

    Append-only — kept around for forensics / "review your sessions"
    panels. Distinct from apps.activity.ActivityEvent which is a
    workspace-wide stream of user actions across the dashboard.
    """
    KIND_CHOICES = [
        ("login",                "Sign in"),
        ("logout",               "Sign out"),
        ("login_failed",         "Sign in failed"),
        ("password_changed",     "Password changed"),
        ("two_factor_enabled",   "Two-factor enabled"),
        ("two_factor_disabled",  "Two-factor disabled"),
        ("api_key_created",      "API key created"),
        ("api_key_revoked",      "API key revoked"),
        ("session_revoked",      "Session signed out (other)"),
        ("data_export_requested", "Data export requested"),
        ("account_deletion_requested", "Account deletion requested"),
        ("account_deletion_canceled",  "Account deletion canceled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    kind = models.CharField(max_length=40, choices=KIND_CHOICES)
    description = models.CharField(max_length=400, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=400, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["kind"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.kind} · {self.created_at}"


def record_audit(user, kind: str, *, description: str = "", request=None,
                 metadata: dict | None = None) -> AuditEvent | None:
    """Convenience helper — call from views after security-relevant actions.

    Pulls IP + user agent from the request when provided. Returns the
    created AuditEvent (or None for anonymous users — there's nothing
    to attribute).
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    ip = ""
    ua = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR", "") or None
        ua = request.META.get("HTTP_USER_AGENT", "")[:400]
    return AuditEvent.objects.create(
        user=user, kind=kind, description=description[:400],
        ip_address=ip or None, user_agent=ua,
        metadata=metadata or {},
    )


# Register TwoFactorDevice so migrations/ORM pick it up.
from .two_factor import TwoFactorDevice  # noqa: F401,E402
