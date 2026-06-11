"""Personal calendar events.

Owner-scoped (one user's events are not visible to others). Single
Event model — no recurring events in v1.
"""
from django.conf import settings
from django.db import models


class Event(models.Model):
    CATEGORY_CHOICES = [
        ("meeting",  "Meeting"),
        ("personal", "Personal"),
        ("deadline", "Deadline"),
        ("holiday",  "Holiday"),
    ]
    CATEGORY_COLORS = {
        "meeting":  "#3b82f6",
        "personal": "#10b981",
        "deadline": "#ef4444",
        "holiday":  "#f59e0b",
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="events",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    all_day = models.BooleanField(default=False)
    category = models.CharField(
        max_length=16, choices=CATEGORY_CHOICES, default="meeting",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        indexes = [models.Index(fields=["owner", "start"])]

    def __str__(self) -> str:
        return f"{self.title} @ {self.start:%Y-%m-%d}"

    @property
    def color(self) -> str:
        return self.CATEGORY_COLORS[self.category]

    def to_fullcalendar(self) -> dict:
        return {
            "id": self.pk,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "allDay": self.all_day,
            "color": self.color,
            "extendedProps": {
                "category": self.category,
                "description": self.description,
            },
        }
