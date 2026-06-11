"""Single global Kanban board cards.

Status enum represents the column. Position is the within-column index;
on move we shift siblings to make room rather than reflow densely.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Card(models.Model):
    STATUS_CHOICES = [
        ("todo",        "To Do"),
        ("in_progress", "In Progress"),
        ("review",      "Review"),
        ("done",        "Done"),
    ]
    PRIORITY_CHOICES = [
        ("low",  "Low"),
        ("med",  "Medium"),
        ("high", "High"),
    ]
    PRIORITY_BORDER = {
        "low":  "border-l-zinc-400",
        "med":  "border-l-blue-500",
        "high": "border-l-red-500",
    }

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="todo")
    priority = models.CharField(max_length=8, choices=PRIORITY_CHOICES, default="med")
    position = models.IntegerField(default=0)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="kanban_cards",
    )
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="created_kanban_cards",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "position", "pk"]
        indexes = [models.Index(fields=["status", "position"])]

    def __str__(self) -> str:
        return self.title

    @property
    def is_overdue(self) -> bool:
        if not self.due_date or self.status == "done":
            return False
        return self.due_date < timezone.now().date()

    @property
    def priority_border_class(self) -> str:
        return self.PRIORITY_BORDER[self.priority]
