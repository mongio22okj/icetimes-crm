"""Organizations + multi-tenant primitives.

Phase 16 ships the foundation:

  - `Organization` — a workspace. Has a slug for URLs, optional logo,
    a "plan" string (free / pro / enterprise — kept loose; we don't
    promote to FK until Phase 17 needs it), and a `created_by`.
  - `Membership` — joins User × Organization with a role enum
    (owner / admin / member / billing / viewer). One row per
    (user, org) pair.
  - `Invitation` — pending email invites with an opaque token; expires
    after INVITATION_TTL_DAYS, marks `accepted_at` once redeemed.

Per-org permission *matrix* (Role + Permission tables, editable per
org) is intentionally deferred. We start with hardcoded role checks
in `apps/organizations/permissions.py` — clean enough to swap to a
matrix later without view rewrites.

Org-scoping every existing model (Customer, Invoice, Order, …) with
nullable `organization` FKs is also deferred. The `OrgScopedMixin`
shipped here is opt-in — apply it as you migrate each list view.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

INVITATION_TTL_DAYS = 14


ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_BILLING = "billing"
ROLE_VIEWER = "viewer"

ROLE_CHOICES = [
    (ROLE_OWNER,   "Owner"),
    (ROLE_ADMIN,   "Admin"),
    (ROLE_MEMBER,  "Member"),
    (ROLE_BILLING, "Billing"),
    (ROLE_VIEWER,  "Viewer"),
]

# Strict ordering used by `role_at_least()`. Anything left of the role
# in this tuple has at least that role's privileges.
ROLE_RANK = {ROLE_OWNER: 0, ROLE_ADMIN: 1, ROLE_BILLING: 2, ROLE_MEMBER: 3, ROLE_VIEWER: 4}


PLAN_CHOICES = [
    ("free", "Free"),
    ("pro", "Pro"),
    ("enterprise", "Enterprise"),
]


class Organization(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_organizations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug_from(self.name)
        super().save(*args, **kwargs)

    @classmethod
    def _unique_slug_from(cls, name: str) -> str:
        base = slugify(name) or "org"
        slug, n = base, 1
        while cls.objects.filter(slug=slug).exists():
            n += 1
            slug = f"{base}-{n}"
        return slug

    def get_absolute_url(self) -> str:
        return reverse("organizations:settings", kwargs={"slug": self.slug})

    def initials(self) -> str:
        parts = self.name.split()
        if len(parts) >= 2:
            return (parts[0][:1] + parts[-1][:1]).upper()
        return (self.name[:2] or "??").upper()


class Membership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="uniq_membership_per_user_per_org",
            ),
        ]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}@{self.organization.slug} · {self.role}"


def role_at_least(membership_role: str, required: str) -> bool:
    """True when `membership_role` has at least the privileges of `required`.

    The owner role is the most-privileged; viewer is least. Roles unknown
    to the rank table return False (defensive — a typo'd role shouldn't
    accidentally elevate privileges).
    """
    a = ROLE_RANK.get(membership_role)
    b = ROLE_RANK.get(required)
    if a is None or b is None:
        return False
    return a <= b


class Invitation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    token = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "accepted_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization.slug} ({self.role})"

    @classmethod
    def generate_token(cls) -> str:
        return secrets.token_urlsafe(32).rstrip("=")

    @classmethod
    def create_for(cls, organization, email: str, role: str,
                   invited_by=None, ttl_days: int = INVITATION_TTL_DAYS,
                   ) -> Invitation:
        return cls.objects.create(
            organization=organization,
            email=email.strip().lower(),
            role=role,
            token=cls.generate_token(),
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=ttl_days),
        )

    def get_absolute_url(self) -> str:
        return reverse("invitation_accept", kwargs={"token": self.token})

    @property
    def is_expired(self) -> bool:
        return self.expires_at < timezone.now()

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and not self.is_expired

    def accept(self, user) -> Membership:
        """Redeem this invitation for `user` (creates Membership; idempotent).

        Caller must ensure user.email matches self.email — we don't
        enforce here so the view can show a friendlier mismatch message.
        """
        if self.accepted_at is None:
            self.accepted_at = timezone.now()
            self.save(update_fields=["accepted_at"])
        membership, _ = Membership.objects.get_or_create(
            user=user, organization=self.organization,
            defaults={"role": self.role},
        )
        return membership
