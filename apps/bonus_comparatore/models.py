from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Bookmaker(models.Model):
    """Sito di scommesse / casinò online (ADM o estero) inserito nel comparatore."""

    CATEGORY_CHOICES = [
        ("sport", "Solo scommesse sportive"),
        ("casino", "Solo casinò"),
        ("both", "Scommesse + Casinò"),
    ]

    LICENSE_CHOICES = [
        ("adm", "ADM (Italia)"),
        ("mga", "MGA (Malta)"),
        ("ukgc", "UKGC (UK)"),
        ("curacao", "Curaçao eGaming"),
        ("other", "Altra licenza"),
        ("none", "Nessuna licenza"),
    ]

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    logo = models.ImageField(upload_to="bookmakers/logos/", blank=True, null=True)
    logo_url = models.URLField(
        blank=True,
        help_text="Alternativa al file: URL pubblico del logo.",
    )

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, default="both")
    license_type = models.CharField(max_length=10, choices=LICENSE_CHOICES, default="adm")
    license_number = models.CharField(max_length=60, blank=True)

    official_url = models.URLField(help_text="URL ufficiale del bookmaker (non affiliato).")
    affiliate_url = models.URLField(
        blank=True,
        help_text="Link affiliato. Se vuoto si usa l'official_url.",
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=0,
        help_text="Voto editoriale 0–5 (es. 4.5).",
    )
    short_description = models.CharField(
        max_length=240,
        blank=True,
        help_text="Una riga che descrive il bookmaker (mostrata in homepage).",
    )
    full_review = models.TextField(
        blank=True,
        help_text="Recensione completa (mostrata nella scheda dedicata).",
    )

    pros = models.TextField(
        blank=True,
        help_text="Elenco punti di forza, uno per riga.",
    )
    cons = models.TextField(
        blank=True,
        help_text="Elenco punti deboli, uno per riga.",
    )

    brand_color = models.CharField(
        max_length=20,
        default="#111827",
        blank=True,
        help_text="Colore di sfondo del banner (es. #ffffff per bianco, #1b5e20 per verde Sisal).",
    )
    cta_color = models.CharField(
        max_length=20,
        default="#ffd600",
        blank=True,
        help_text="Colore del bottone CTA nel banner (es. #1565c0 per blu).",
    )
    cta_text_color = models.CharField(
        max_length=20,
        default="#111111",
        blank=True,
        help_text="Colore del testo nel bottone CTA (es. #ffffff per bianco).",
    )
    brand_text_dark = models.BooleanField(
        default=False,
        help_text="Testo scuro (nero) sul banner. Spuntare per sfondi chiari (es. Lottomatica bianco).",
    )

    is_published = models.BooleanField(
        default=True,
        help_text="Se False, il bookmaker non appare sul sito pubblico.",
    )
    order = models.PositiveIntegerField(
        default=100,
        help_text="Ordinamento (più basso = più in alto).",
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-rating", "name"]
        verbose_name = "Bookmaker"
        verbose_name_plural = "Bookmaker"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def target_url(self):
        return self.affiliate_url or self.official_url

    @property
    def has_affiliate(self):
        return bool(self.affiliate_url)

    @property
    def primary_bonus(self):
        return self.bonuses.filter(is_active=True).order_by("order", "-updated_at").first()

    @property
    def pros_list(self):
        return [line.strip() for line in self.pros.splitlines() if line.strip()]

    @property
    def cons_list(self):
        return [line.strip() for line in self.cons.splitlines() if line.strip()]


class Bonus(models.Model):
    """Singola promozione/bonus collegata a un Bookmaker."""

    BONUS_TYPE_CHOICES = [
        ("welcome_sport", "Benvenuto scommesse"),
        ("welcome_casino", "Benvenuto casinò"),
        ("freebet", "Free bet"),
        ("freespin", "Free spin"),
        ("cashback", "Cashback / rimborso"),
        ("no_deposit", "Senza deposito"),
        ("reload", "Ricarica"),
        ("other", "Altro"),
    ]

    bookmaker = models.ForeignKey(
        Bookmaker, related_name="bonuses", on_delete=models.CASCADE
    )

    bonus_type = models.CharField(
        max_length=20, choices=BONUS_TYPE_CHOICES, default="welcome_sport"
    )
    title = models.CharField(
        max_length=160,
        help_text='Es. "Bonus benvenuto fino a 100€" o "200% fino a 1000€ + 50 free spin".',
    )
    amount_text = models.CharField(
        max_length=80,
        blank=True,
        help_text='Importo sintetico, es. "100€", "1000€ + 50 FS".',
    )
    description = models.TextField(blank=True)
    terms_summary = models.TextField(
        blank=True,
        help_text="Sintesi dei termini chiave (deposito minimo, requisiti di scommessa, scadenza).",
    )
    terms_url = models.URLField(blank=True, help_text="Link ai T&C completi sul sito del bookmaker.")

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(
        default=False,
        help_text="Mostra in evidenza nelle griglie del comparatore.",
    )

    order = models.PositiveIntegerField(default=100)

    manual_override = models.BooleanField(
        default=False,
        help_text="Se True, lo scraper automatico non sovrascrive questo bonus.",
    )

    scrape_source_url = models.URLField(
        blank=True,
        help_text="URL della pagina promozioni del bookmaker usata dallo scraper.",
    )
    last_scraped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-updated_at"]
        verbose_name = "Bonus"
        verbose_name_plural = "Bonus"

    def __str__(self):
        return f"{self.bookmaker.name} — {self.title}"


class ClickLog(models.Model):
    """Click in uscita verso un bookmaker (dal pulsante 'Ottieni il bonus').

    Registrato dalla view di redirect `BookmakerGoView`. Serve a capire quali
    bookmaker generano più click (e quindi convertono) senza dipendere da
    analytics esterni. `to_affiliate` distingue i click verso un link affiliato
    (monetizzabili) da quelli verso il sito ufficiale (placeholder).
    """

    bookmaker = models.ForeignKey(
        Bookmaker, related_name="clicks", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    referer = models.URLField(max_length=500, blank=True)
    to_affiliate = models.BooleanField(
        default=False,
        help_text="True se il click è andato a un link affiliato (non al sito ufficiale).",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Click"
        verbose_name_plural = "Click log"
        indexes = [
            models.Index(fields=["bookmaker", "created_at"]),
        ]

    def __str__(self):
        return f"{self.bookmaker.name} @ {self.created_at:%d/%m/%Y %H:%M}"
