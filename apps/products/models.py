from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]
    THEME_LIGHT = "light"
    THEME_DARK = "dark"
    THEME_CHOICES = ((THEME_LIGHT, "Chiaro"), (THEME_DARK, "Scuro"))

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS, default="draft")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Landing-page customization (public URL: /p/<slug>/). ────────────
    badge = models.CharField(
        max_length=80, blank=True,
        help_text='Mini-badge sopra il titolo, es. "🔥 OFFERTA LIMITATA".')
    cta_label = models.CharField(
        max_length=60, default="Acquista ora",
        help_text="Testo del bottone di acquisto.")
    accent_color = models.CharField(
        max_length=20, default="#f59e0b",
        help_text="Colore esadecimale del bottone (es. #6366f1, #10b981).")
    theme = models.CharField(
        max_length=10, choices=THEME_CHOICES, default=THEME_LIGHT)
    success_message = models.CharField(
        max_length=200, default="Grazie! Ti contatteremo presto.",
        help_text="Mostrato dopo l'invio quando NON c'è redirect.")
    redirect_url = models.URLField(
        blank=True,
        help_text="Se impostato, redirect alla URL dopo l'invio.")

    # ── Status API (push esterno quando lo stato della Sale cambia). ────
    status_api_url = models.URLField(
        "URL API status", blank=True,
        help_text="Endpoint che riceve POST quando una Sale viene marcata "
                  "sold/lost. Vuoto = nessuna notifica esterna.")
    status_api_key = models.CharField(
        "Chiave API status", max_length=255, blank=True,
        help_text="Inviata in header X-API-Key e nel body come api_key.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_landing_url(self) -> str:
        return reverse("product_landing", kwargs={"slug": self.slug})


class Sale(models.Model):
    """A purchase attempt captured from a product landing page.

    Created with status=pending when a visitor submits the form.
    Operator (or external API webhook) marks it sold / lost later.
    On status change, the CRM POSTs to product.status_api_url so an
    external service can react in real time.
    """
    STATUS_PENDING = "pending"
    STATUS_SOLD = "sold"
    STATUS_LOST = "lost"
    STATUS_CHOICES = (
        (STATUS_PENDING, "In attesa"),
        (STATUS_SOLD, "Venduto"),
        (STATUS_LOST, "Mancato acquisto"),
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="sales")
    firstname = models.CharField(max_length=120)
    lastname = models.CharField(max_length=120)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=8, blank=True, default="IT")

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
        db_index=True)
    sold_at = models.DateTimeField(null=True, blank=True)

    api_response = models.JSONField(default=dict, blank=True,
                                    help_text="Ultima risposta della Product.status_api_url.")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale #{self.pk} — {self.product.name} · {self.email}"

    @property
    def full_name(self):
        return f"{self.firstname} {self.lastname}".strip()
