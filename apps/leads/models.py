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
        help_text="Timestamp riportato da TrackBox, se presente nel postback.",
    )
    uniqueid = models.CharField(max_length=128, blank=True, db_index=True)
    firstname = models.CharField(max_length=120, blank=True)
    lastname = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=8, blank=True)
    status = models.CharField(max_length=120, blank=True)
    is_deposit = models.BooleanField(default=False)
    source = models.CharField(max_length=32, default="postback")
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name or self.email or self.uniqueid or f"Lead {self.pk}"

    @property
    def full_name(self):
        return f"{self.firstname} {self.lastname}".strip()
