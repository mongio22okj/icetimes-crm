from django.conf import settings
from django.db import models


class WizardSubmission(models.Model):
    THEME_CHOICES = [("light", "Light"), ("dark", "Dark"), ("system", "System")]
    TEAM_SIZE_CHOICES = [
        ("1", "Just me"),
        ("2-10", "2 – 10"),
        ("11-50", "11 – 50"),
        ("50+", "50+"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="wizard_submissions",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=120, blank=True)
    role = models.CharField(max_length=80, blank=True)
    team_size = models.CharField(max_length=10, choices=TEAM_SIZE_CHOICES, blank=True)
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default="system")
    notifications_enabled = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.email})"
