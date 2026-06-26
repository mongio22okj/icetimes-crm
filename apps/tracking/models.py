import secrets

from django.db import models
from django.utils import timezone


class TrackboxBroker(models.Model):
    """Configurazione API di un broker TrackBox (es. FINTECHGURUS).

    Un modello DEDICATO per il tipo TrackBox: contiene SOLO i campi che
    servono a questo broker. Altri tipi di broker avranno un loro modello
    separato, così ogni integrazione resta isolata e senza campi inutili.

    Endpoint derivati dal base_url:
      push → {base_url}/api/signup/procform   (header x-api-key = push_key)
      pull → {base_url}/api/pull/customers     (header x-api-key = pull_key)
    """

    name = models.CharField(
        "Nome", max_length=120,
        help_text="Etichetta interna, es. 'FINTECHGURUS'.")
    base_url = models.URLField(
        "Base URL", help_text="Es. https://track.fintechgurus.org")
    username = models.CharField(
        "Username", max_length=120,
        help_text="Header x-trackbox-username.")
    password = models.CharField(
        "Password", max_length=255,
        help_text="Header x-trackbox-password.")
    push_key = models.CharField(
        "x-api-key PUSH", max_length=255,
        help_text="Chiave x-api-key per il PUSH (/api/signup/procform).")
    pull_key = models.CharField(
        "x-api-key PULL", max_length=255,
        help_text="Chiave x-api-key per il PULL (/api/pull/customers) — "
                  "DIVERSA dalla push.")
    ai = models.CharField("ai (affiliate id)", max_length=64)
    ci = models.CharField("ci", max_length=64, default="1")
    gi = models.CharField("gi (group id)", max_length=64)

    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Nome funnel inviato al broker nel campo 'so' (visibile nei "
                  "report TrackBox). Se vuoto usa il nome del broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Slug della landing pubblica: /lp/<slug>/. Lascia vuoto "
                  "se il broker non usa una landing dedicata.")

    note = models.CharField(
        "Note", max_length=255, blank=True,
        help_text="Nota interna / nome alternativo del broker.")

    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker TrackBox"
        verbose_name_plural = "Broker TrackBox"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/signup/procform"

    @property
    def pull_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/pull/customers"


class Lead(models.Model):
    """Un lead catturato dal CRM, agganciato a un broker.

    `click_id` è il NOSTRO identificativo univoco (= affclickid) che inviamo
    al broker al push e che il broker ci rimanda nel postback: è la chiave
    con cui ricolleghiamo gli aggiornamenti di stato/FTD al lead esatto.
    `broker_lead_id` è invece l'id che ci ritorna il broker (customerId/uniqueid).
    """

    broker = models.ForeignKey(
        TrackboxBroker, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="leads",
        help_text="Broker di destinazione del lead.")

    click_id = models.CharField(
        "Click id (affclickid)", max_length=64, unique=True, db_index=True,
        help_text="Id univoco nostro, chiave di aggancio del postback.")
    broker_lead_id = models.CharField(
        "Id lead broker", max_length=128, blank=True, db_index=True,
        help_text="Id ritornato dal broker al push (customerId/uniqueid).")

    firstname = models.CharField("Nome", max_length=120, blank=True)
    lastname = models.CharField("Cognome", max_length=120, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Telefono", max_length=40, blank=True)
    country = models.CharField("Paese", max_length=8, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)

    status = models.CharField("Stato", max_length=120, blank=True)
    is_deposit = models.BooleanField("FTD", default=False)

    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    event_at = models.DateTimeField("Data evento", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Lead"
        verbose_name_plural = "Lead"

    def __str__(self) -> str:
        return self.full_name or self.email or self.click_id

    @property
    def full_name(self) -> str:
        return f"{self.firstname} {self.lastname}".strip()

    @staticmethod
    def gen_click_id() -> str:
        return "ice" + secrets.token_hex(8)

    def save(self, *args, **kwargs):
        if not self.click_id:
            cid = self.gen_click_id()
            while Lead.objects.filter(click_id=cid).exists():
                cid = self.gen_click_id()
            self.click_id = cid
        super().save(*args, **kwargs)


class PushLog(models.Model):
    """Esito di un tentativo di PUSH di un lead verso il broker."""

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE,
                             related_name="push_logs")
    broker = models.ForeignKey(TrackboxBroker, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="push_logs")
    success = models.BooleanField(default=False)
    response = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Push log"
        verbose_name_plural = "Push log"

    def __str__(self) -> str:
        return f"Push lead {self.lead_id} → {'ok' if self.success else 'fail'}"
