from django.db import models
from django.urls import reverse
from django.utils import timezone


class SupportTicket(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.subject} — {self.email}"


class LandingPage(models.Model):
    """A configurable public landing page that captures leads.

    Each row drives one public URL (`/landing/<slug>/`). Copy, colors,
    pre-set tracking values (funnel/source/sub), and form variant are all
    editable from the CRM — duplicating a landing for a new ad campaign
    is a row insert, not a code change.
    """

    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_CHOICES = (
        (THEME_LIGHT, "Chiaro"),
        (THEME_DARK, "Scuro"),
    )

    VARIANT_FULL = "full"
    VARIANT_EMAIL = "email"
    VARIANT_CHOICES = (
        (VARIANT_FULL, "Form completo (nome, cognome, email, telefono, paese)"),
        (VARIANT_EMAIL, "Solo email"),
    )

    slug = models.SlugField(unique=True, max_length=80,
                            help_text="Parte finale dell'URL. Es. \"trading-2026-A\".")
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    badge = models.CharField(
        max_length=80, blank=True,
        help_text="Mini-badge sopra il titolo, es. \"🔥 OFFERTA LIMITATA\"."
    )
    cta_label = models.CharField(max_length=60, default="Accedi ora",
                                 help_text="Testo del bottone di invio.")

    theme = models.CharField(max_length=10, choices=THEME_CHOICES,
                             default=THEME_LIGHT)
    accent_color = models.CharField(
        max_length=20, default="#f59e0b",
        help_text="Colore esadecimale del bottone (es. #6366f1, #10b981)."
    )

    form_variant = models.CharField(max_length=10, choices=VARIANT_CHOICES,
                                    default=VARIANT_FULL)

    # Tracking values pre-impostati salvati con ogni lead della landing.
    funnel = models.CharField(max_length=120, blank=True,
                              help_text="Nome funnel/campagna. Es. \"trading-2026-A\".")
    source_tag = models.CharField("Source", max_length=64, blank=True,
                                  help_text="Canale, es. FB, GoogleAds, TikTok.")
    sub = models.CharField(max_length=120, blank=True,
                           help_text="ID ad set / keyword / sub-id.")

    success_message = models.CharField(
        max_length=200, default="Grazie! Ti contatteremo presto.",
        help_text="Mostrato dopo l'invio quando NON c'è redirect."
    )
    redirect_url = models.URLField(
        blank=True,
        help_text="Se impostato, il browser viene reindirizzato qui dopo l'invio."
    )

    is_active = models.BooleanField(default=True,
                                    help_text="Se OFF, la URL pubblica risponde 404.")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.slug})"

    def get_absolute_url(self) -> str:
        return reverse("marketing:landing_public", kwargs={"slug": self.slug})
