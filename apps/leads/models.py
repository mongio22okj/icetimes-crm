from django.db import models
from django.urls import reverse
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
    country = models.CharField(max_length=8, blank=True, db_index=True)
    status = models.CharField(max_length=120, blank=True, db_index=True)
    is_deposit = models.BooleanField(default=False)
    source = models.CharField(max_length=64, default="postback", db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    score = models.PositiveSmallIntegerField(
        default=0,
        help_text="Qualità del lead 0-100. Calcolato automaticamente in "
                  "base alla completezza/validità dei dati al postback.")

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
    KIND_MEDIAFRONT = "mediafront"
    KIND_SPMMONSTER = "spmmonster"
    # Tipi di API rimossi dal sito su richiesta utente: nessuna integrazione
    # selezionabile. I costanti restano definiti per non rompere gli import.
    KIND_CHOICES = ()

    # Kinds that can pull/refresh data, and kinds that can receive pushes.
    PULL_KINDS = ()
    PUSH_KINDS = ()

    name = models.CharField(max_length=120)
    logo_url = models.URLField(
        "Foto / Logo (URL)", blank=True,
        help_text="Link a un'immagine (logo del broker). Mostrato accanto al nome.")
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

    # ── Ping-tree dispatch + payout (2026 best practices). ─────────────
    priority = models.PositiveIntegerField(
        default=100, db_index=True,
        help_text="Ordine ping-tree: numero più basso = priorità più alta. "
                  "Il dispatch prova prima il broker con priority minore.")
    auto_dispatch = models.BooleanField(
        default=False,
        help_text="Se ON, al postback il CRM avvia automaticamente il "
                  "dispatch ping-tree per leads ricevuti da questo source.")
    payout_per_ftd = models.DecimalField(
        "Payout per FTD (€)", max_digits=10, decimal_places=2, default=0,
        help_text="Quanto ti paga il broker per ogni FTD verificato.")
    payout_per_lead = models.DecimalField(
        "Payout per lead (€)", max_digits=10, decimal_places=2, default=0,
        help_text="Quanto ti paga il broker per ogni lead consegnato (anche senza FTD).")
    duplicate_window_hours = models.PositiveIntegerField(
        "Finestra antiduplicato (ore)", default=24,
        help_text="Un lead con stessa email/uniqueid arrivato entro N ore "
                  "viene marcato come duplicato. 0 = disabilita controllo.")

    # ── Public broker landing /b/<landing_slug>/ ────────────────────────
    landing_active = models.BooleanField(
        "Landing pubblica attiva", default=False,
        help_text="Se ON, /b/<landing_slug>/ risponde con la landing del broker.")
    landing_slug = models.SlugField(
        "Slug landing", max_length=80, blank=True,
        help_text="URL: /b/<slug>/. Esempio: broker1-crypto.")
    landing_hero_title = models.CharField(
        "Hero — titolo", max_length=200, blank=True,
        default="Inizia a investire oggi")
    landing_hero_subtitle = models.TextField(
        "Hero — sottotitolo", blank=True,
        default="La piattaforma più affidabile. Registrati in 2 minuti.")
    landing_features = models.TextField(
        "Hero — features (1 per riga)", blank=True,
        help_text="Una feature per riga. Es: \"Regolamentato CONSOB & CySEC\".")
    landing_trust_badges = models.TextField(
        "Trust badges (1 per riga)", blank=True,
        help_text="Badge piccoli sotto il form. Es: \"SSL Sicuro\", \"GDPR\", \"4.8/5\".")
    LANDING_THEME_GRADIENT = "gradient"
    LANDING_THEME_LIGHT = "light"
    LANDING_THEME_DARK = "dark"
    LANDING_THEME_CHOICES = (
        (LANDING_THEME_GRADIENT, "Gradient viola/blu"),
        (LANDING_THEME_LIGHT, "Chiaro"),
        (LANDING_THEME_DARK, "Scuro"),
    )
    landing_theme = models.CharField(
        "Tema", max_length=20, choices=LANDING_THEME_CHOICES,
        default=LANDING_THEME_GRADIENT)
    landing_accent_color = models.CharField(
        "Colore accent", max_length=20, default="#667eea",
        help_text="Colore esadecimale del bottone CTA.")
    landing_cta_label = models.CharField(
        "Label CTA", max_length=80, default="Crea Account Gratis")
    landing_redirect_url = models.URLField(
        "Redirect post-submit", blank=True,
        help_text="Vuoto = mostra messaggio inline.")
    landing_success_message = models.CharField(
        "Messaggio successo", max_length=200,
        default="Grazie! Ti contatteremo entro pochi minuti.")

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    def get_landing_url(self):
        from django.urls import reverse
        if self.landing_slug:
            return reverse("broker_landing", kwargs={"slug": self.landing_slug})
        return ""

    @property
    def hero_features_list(self):
        return [line.strip() for line in (self.landing_features or "").splitlines() if line.strip()]

    @property
    def trust_badges_list(self):
        return [line.strip() for line in (self.landing_trust_badges or "").splitlines() if line.strip()]

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


class Partner(models.Model):
    """An external partner / affiliate the CRM tracks for traffic attribution.

    Lighter than LeadSource: just an ID slug, a display name, an optional
    landing URL and API key, plus a free-text note. Useful for registering
    partners that drive traffic to our landings or that we forward leads
    to manually.
    """

    slug = models.SlugField(
        "ID Partner", unique=True, max_length=80,
        help_text="Univoco, caratteri latini (lettere, numeri, underscore, trattini)."
    )
    name = models.CharField(
        "Nome", max_length=200,
        help_text="Nome visualizzato. Es. \"Partner #1\"."
    )
    landing_url = models.URLField(
        "URL della landing", blank=True,
        help_text="URL della landing del partner (esterna)."
    )
    api_key = models.CharField(
        "Chiave API (loro)", max_length=255, blank=True,
        help_text="Opzionale — chiave API del partner, se serve per inviargli qualcosa."
    )
    webhook_token = models.CharField(
        "Token postback (nostro)", max_length=64, blank=True, unique=False,
        help_text="Token segreto che il partner usa per fare POST a "
                  "/in/<slug>/?token=<token>. Auto-generato al primo save."
    )
    note = models.TextField(
        "Nota", blank=True,
        help_text="Promemoria interno. Non viene mostrato pubblicamente."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.webhook_token:
            import secrets
            self.webhook_token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("leads:partner_edit", kwargs={"pk": self.pk})

    def get_postback_path(self) -> str:
        return f"/in/{self.slug}/?token={self.webhook_token}"


class Campaign(models.Model):
    """Ad-platform campaign tracking. Budget vs spend vs leads → CPA.

    Standalone from LeadSource (broker config) — a campaign is what
    drives traffic to a landing, the broker is where leads are pushed.
    """

    PLATFORM_FACEBOOK = "facebook"
    PLATFORM_GOOGLE = "google"
    PLATFORM_TIKTOK = "tiktok"
    PLATFORM_INSTAGRAM = "instagram"
    PLATFORM_LINKEDIN = "linkedin"
    PLATFORM_OTHER = "other"
    PLATFORM_CHOICES = (
        (PLATFORM_FACEBOOK, "Facebook Ads"),
        (PLATFORM_GOOGLE, "Google Ads"),
        (PLATFORM_TIKTOK, "TikTok Ads"),
        (PLATFORM_INSTAGRAM, "Instagram Ads"),
        (PLATFORM_LINKEDIN, "LinkedIn Ads"),
        (PLATFORM_OTHER, "Altro"),
    )

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Attiva"),
        (STATUS_PAUSED, "In pausa"),
        (STATUS_COMPLETED, "Completata"),
    )

    name = models.CharField("Nome campagna", max_length=200)
    platform = models.CharField("Piattaforma", max_length=20,
                                choices=PLATFORM_CHOICES,
                                default=PLATFORM_FACEBOOK)
    budget = models.DecimalField("Budget (€)", max_digits=12, decimal_places=2,
                                 default=0)
    spent = models.DecimalField("Spesa (€)", max_digits=12, decimal_places=2,
                                default=0,
                                help_text="Spesa totale ad oggi su questa campagna.")
    clicks = models.PositiveIntegerField(default=0)
    leads_count = models.PositiveIntegerField(
        "Lead", default=0,
        help_text="Lead ricevuti dalla campagna. Aggiornabile manualmente "
                  "o (futuro) calcolabile via funnel/source tracking.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default=STATUS_ACTIVE, db_index=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} · {self.get_platform_display()}"

    @property
    def cpa(self):
        if not self.leads_count:
            return None
        return self.spent / self.leads_count

    @property
    def remaining_budget(self):
        return self.budget - self.spent

    @property
    def budget_used_pct(self):
        if not self.budget:
            return 0
        return min(100, float(self.spent) * 100 / float(self.budget))


class NotificationWebhook(models.Model):
    """Outbound webhook fired on CRM events (new lead, FTD, errors).

    Lets the operator wire Slack/Discord/Telegram alerts so leads are
    actioned immediately — directly tackles the "speed-to-lead" best
    practice (every hour of delay kills FTD conversion).
    """

    KIND_SLACK = "slack"
    KIND_DISCORD = "discord"
    KIND_TELEGRAM = "telegram"
    KIND_GENERIC = "generic"
    KIND_CHOICES = (
        (KIND_SLACK, "Slack incoming webhook"),
        (KIND_DISCORD, "Discord webhook"),
        (KIND_TELEGRAM, "Telegram bot (sendMessage)"),
        (KIND_GENERIC, "Generic JSON POST"),
    )

    EVENT_NEW_LEAD = "new_lead"
    EVENT_FTD = "ftd"
    EVENT_SALE_SOLD = "sale_sold"
    EVENT_API_ERROR = "api_error"
    EVENT_LABELS = {
        EVENT_NEW_LEAD: "Nuovo lead",
        EVENT_FTD: "FTD",
        EVENT_SALE_SOLD: "Vendita venduta",
        EVENT_API_ERROR: "Errore API",
    }

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES,
                            default=KIND_SLACK)
    url = models.URLField(
        "Webhook URL",
        help_text="Slack/Discord: la URL di incoming webhook. "
                  "Telegram: https://api.telegram.org/bot<TOKEN>/sendMessage. "
                  "Generic: qualsiasi endpoint che accetta POST JSON.")
    telegram_chat_id = models.CharField(
        "Telegram chat_id", max_length=64, blank=True,
        help_text="Solo per Telegram — chat_id dove inviare il messaggio.")

    on_new_lead = models.BooleanField("Nuovo lead", default=True)
    on_ftd = models.BooleanField("FTD", default=True)
    on_sale_sold = models.BooleanField("Vendita venduta", default=True)
    on_api_error = models.BooleanField("Errore API", default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    def fires_for(self, event):
        return {
            self.EVENT_NEW_LEAD: self.on_new_lead,
            self.EVENT_FTD: self.on_ftd,
            self.EVENT_SALE_SOLD: self.on_sale_sold,
            self.EVENT_API_ERROR: self.on_api_error,
        }.get(event, False)


class DispatchLog(models.Model):
    """One row per ping-tree attempt: which broker, when, success, latency."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE,
                             related_name="dispatch_logs")
    source = models.ForeignKey(LeadSource, on_delete=models.SET_NULL,
                               null=True, related_name="dispatch_logs")
    source_name = models.CharField(max_length=120, blank=True,
                                   help_text="Snapshot del nome al momento del dispatch.")
    attempted_at = models.DateTimeField(default=timezone.now, db_index=True)
    success = models.BooleanField(default=False)
    response = models.JSONField(default=dict, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-attempted_at"]

    def __str__(self):
        return f"Lead {self.lead_id} → {self.source_name} ({'ok' if self.success else 'fail'})"


class AutoMessage(models.Model):
    """Email template fired automatically on CRM events.

    Speed-to-lead: the first touchpoint should happen within minutes.
    These messages auto-send via Django's email backend when triggered.
    """

    TRIGGER_NEW_LEAD = "new_lead"
    TRIGGER_FTD = "ftd"
    TRIGGER_CHOICES = (
        (TRIGGER_NEW_LEAD, "Nuovo lead"),
        (TRIGGER_FTD, "FTD"),
    )

    name = models.CharField(max_length=120)
    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES,
                               default=TRIGGER_NEW_LEAD)
    subject = models.CharField(
        max_length=200,
        help_text="Variabili: {{firstname}}, {{lastname}}, {{email}}, {{country}}.")
    body = models.TextField(
        help_text="Plain text. Variabili: {{firstname}}, {{lastname}}, "
                  "{{email}}, {{phone}}, {{country}}, {{status}}.")
    from_email = models.EmailField(blank=True,
                                   help_text="Vuoto = usa DEFAULT_FROM_EMAIL.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trigger", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()})"


class LandingVisit(models.Model):
    """Visita tracciata su una landing page esterna."""
    session_id = models.CharField(max_length=255, db_index=True)
    page = models.CharField(max_length=255)
    utm_source = models.CharField(max_length=255, blank=True, null=True)
    utm_campaign = models.CharField(max_length=255, blank=True, null=True)
    utm_medium = models.CharField(max_length=255, blank=True, null=True)
    utm_content = models.CharField(max_length=255, blank=True, null=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Visit {self.session_id[:8]} — {self.page}"


class LandingClick(models.Model):
    """Click su un bottone CTA tracciato da una landing page esterna."""
    session_id = models.CharField(max_length=255, db_index=True)
    button_name = models.CharField(max_length=255)
    page = models.CharField(max_length=255)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Click '{self.button_name}' — {self.session_id[:8]}"


class TrackingLink(models.Model):
    """Link corto di tracciamento (es. /t/jJzR86).

    Al click registra una visita e reindirizza alla destinazione,
    aggiungendo `cid=<code>` così il postback del broker si può
    riagganciare al click originale.
    """

    code = models.CharField(max_length=12, unique=True, db_index=True,
                            help_text="Codice corto auto-generato (es. jJzR86).")
    name = models.CharField(max_length=120, blank=True,
                            help_text="Etichetta interna (es. 'FB - IREV crypto').")
    source = models.ForeignKey(
        "LeadSource", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tracking_links",
        help_text="Broker associato (opzionale).")
    destination = models.URLField(
        help_text="Dove reindirizzare il click (landing del broker o offerta).")
    clicks = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"/t/{self.code} → {self.name or self.destination}"

    @staticmethod
    def _gen_code(length: int = 6) -> str:
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def save(self, *args, **kwargs):
        if not self.code:
            code = self._gen_code()
            while TrackingLink.objects.filter(code=code).exists():
                code = self._gen_code()
            self.code = code
        super().save(*args, **kwargs)

    def get_short_path(self) -> str:
        return f"/t/{self.code}"


class SyncAudit(models.Model):
    """Log di ogni sincronizzazione leads da sorgenti esterne."""

    ACTION_SYNC = "sync"
    ACTION_ERROR = "error"

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    action = models.CharField(max_length=50, default=ACTION_SYNC)
    source = models.CharField(max_length=120, blank=True)
    processed = models.PositiveIntegerField(default=0)
    created = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    details = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Sync Audit"
        verbose_name_plural = "Sync Audits"

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.action} ({self.source or 'all'})"
