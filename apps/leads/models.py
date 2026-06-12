from django.db import models
from django.utils import timezone


class Lead(models.Model):
    """A lead received from TrackBox (postback) or sent manually.

    Postbacks upsert on `uniqueid` (TrackBox id) falling back to email,
    so status updates and deposit events land on the same row.
    """

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    event_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp riportato dalla fonte, se presente nel postback.",
    )
    uniqueid = models.CharField(max_length=128, blank=True, db_index=True)
    firstname = models.CharField(max_length=120, blank=True)
    lastname = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=120, blank=True)
    is_deposit = models.BooleanField(default=False)
    source = models.CharField(max_length=64, default="postback")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or self.email or self.uniqueid or f"Lead {self.pk}"

    @property
    def full_name(self):
        return f"{self.firstname} {self.lastname}".strip()


class LeadSource(models.Model):
    """A configurable external lead API (TrackBox / IREV / Affinitrax).

    Lets the operator add and edit API connections from the CRM UI
    instead of editing server environment variables. Each `kind` knows
    which fields it needs; the form shows hints accordingly.
    """

    KIND_TRACKBOX = "trackbox"
    KIND_IREV = "irev"
    KIND_AFFINITRAX = "affinitrax"
    KIND_V3 = "v3"
    KIND_CHOICES = (
        (KIND_TRACKBOX, "TrackBox"),
        (KIND_IREV, "IREV"),
        (KIND_AFFINITRAX, "Affinitrax"),
        (KIND_V3, "Integration v3 (api_token)"),
    )

    # Kinds that can pull/refresh data, and kinds that can receive pushes.
    PULL_KINDS = (KIND_TRACKBOX, KIND_IREV, KIND_AFFINITRAX)
    PUSH_KINDS = (KIND_TRACKBOX, KIND_IREV, KIND_AFFINITRAX, KIND_V3)

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    base_url = models.URLField(help_text="Es. https://stylishwnt.com")
    is_active = models.BooleanField(default=True)

    # Generic secret: TrackBox x-api-key, IREV token, Affinitrax afx_ key.
    token = models.CharField("Token / API key", max_length=255, blank=True)

    # TrackBox extras.
    username = models.CharField(max_length=120, blank=True,
                                help_text="Solo TrackBox")
    password = models.CharField(max_length=255, blank=True,
                                help_text="Solo TrackBox")
    ai = models.CharField("ai", max_length=64, blank=True,
                          help_text="Solo TrackBox")
    ci = models.CharField("ci", max_length=64, blank=True, default="1",
                          help_text="Solo TrackBox")
    gi = models.CharField("gi", max_length=64, blank=True,
                          help_text="Solo TrackBox")

    # IREV extras.
    affiliate_id = models.CharField(max_length=64, blank=True,
                                    help_text="Solo IREV")
    offer_id = models.CharField(max_length=64, blank=True,
                                help_text="IREV / Affinitrax")
    goal_lead = models.CharField("Goal UUID lead", max_length=64, blank=True,
                                 help_text="Solo IREV")
    goal_ftd = models.CharField("Goal UUID FTD", max_length=64, blank=True,
                                help_text="Solo IREV")

    # Integration v3 extras (POST /api/v3/integration?api_token=…).
    link_id = models.CharField(max_length=64, blank=True,
                               help_text="Solo Integration v3")
    funnel = models.CharField(max_length=120, blank=True,
                              help_text="Solo Integration v3")
    source_tag = models.CharField("Source", max_length=64, blank=True,
                                  help_text="Solo Integration v3 (es. FB)")

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    @property
    def can_pull(self) -> bool:
        return self.kind in self.PULL_KINDS

    @property
    def can_push(self) -> bool:
        return self.kind in self.PUSH_KINDS

    @property
    def slug(self) -> str:
        """Stable per-source tag stored on Lead.source."""
        return f"{self.kind}-{self.pk}" if self.pk else self.kind
