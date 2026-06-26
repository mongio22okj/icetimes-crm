import secrets

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


def _push_result(success, response=None, broker_lead_id="", login_url="", error=""):
    """Forma normalizzata del risultato di un push, uguale per ogni broker."""
    return {
        "success": success,
        "broker_lead_id": broker_lead_id,
        "login_url": login_url,
        "error": error,
        "response": response if isinstance(response, dict) else {},
    }


class TrackboxBroker(models.Model):
    """Configurazione API di un broker TrackBox (es. FINTECHGURUS).

    Un modello DEDICATO per il tipo TrackBox: contiene SOLO i campi che
    servono a questo broker. Endpoint dal base_url:
      push → {base_url}/api/signup/procform   (x-api-key = push_key)
      pull → {base_url}/api/pull/customers     (x-api-key = pull_key)
    """

    kind = "trackbox"
    kind_label = "TrackBox"

    name = models.CharField(
        "Nome", max_length=120,
        help_text="Etichetta interna, es. 'FINTECHGURUS'.")
    base_url = models.URLField(
        "Base URL", help_text="Es. https://track.fintechgurus.org")
    username = models.CharField(
        "Username", max_length=120, help_text="Header x-trackbox-username.")
    password = models.CharField(
        "Password", max_length=255, help_text="Header x-trackbox-password.")
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
        help_text="Nome funnel inviato nel campo 'so'. Se vuoto usa il nome.")
    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
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

    def push(self, lead):
        from . import trackbox
        try:
            resp = trackbox.push_lead(self, lead) or {}
            return _push_result(
                True, resp,
                broker_lead_id=trackbox.extract_broker_lead_id(resp),
                login_url=trackbox.extract_login_url(resp))
        except trackbox.TrackboxError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class IrevBroker(models.Model):
    """Configurazione API di un broker IREV (Lead Distribution Affiliate v2).

    Modello dedicato (credenziali e parametri solo suoi). Auth a token unico.
    Push → {base_url}/api/affiliates/v2/leads. Stato via POSTBACK (aggancio
    per lead_uuid = broker_lead_id). FTD riconosciuto da status/goal FTD.
    """

    kind = "irev"
    kind_label = "IREV"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField("Base URL", help_text="Es. https://stylishwnt.com")
    token = models.CharField(
        "API token", max_length=255, help_text="Header Authorization.")
    affiliate_id = models.CharField("affiliate_id", max_length=64)
    offer_id = models.CharField("offer_id", max_length=64)
    goal_lead_uuid = models.CharField(
        "Goal UUID Lead", max_length=64, blank=True)
    goal_ftd_uuid = models.CharField(
        "Goal UUID FTD", max_length=64, blank=True,
        help_text="UUID del goal FTD: serve a riconoscere i depositi.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    note = models.CharField("Note", max_length=255, blank=True)

    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker IREV"
        verbose_name_plural = "Broker IREV"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/affiliates/v2/leads"

    def push(self, lead):
        from . import irev
        try:
            resp = irev.push_lead(self, lead) or {}
            return _push_result(
                True, resp,
                broker_lead_id=irev.extract_broker_lead_id(resp),
                login_url=irev.extract_login_url(resp))
        except irev.IrevError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


# Tipi di broker registrati: kind → modello. Per risolvere slug/landing e
# costruire elenchi unificati senza accoppiare il resto del codice.
BROKER_MODELS = (TrackboxBroker, IrevBroker)


def find_broker_by_slug(slug):
    for model in BROKER_MODELS:
        b = model.objects.filter(landing_slug=slug, is_active=True).first()
        if b:
            return b
    return None


def all_brokers():
    out = []
    for model in BROKER_MODELS:
        out.extend(model.objects.all())
    return out


class Lead(models.Model):
    """Un lead catturato dal CRM, agganciato a UN broker (di qualsiasi tipo).

    `click_id` = nostro id univoco (affclickid). `broker_lead_id` = id che
    ci ritorna il broker al push (TrackBox: customerId/uniqueid; IREV: lead_uuid),
    su cui agganciamo i postback di stato/FTD. Il broker è un riferimento
    GENERICO: può puntare a un TrackboxBroker o a un IrevBroker.
    """

    # Riferimento generico al broker (TrackBox / IREV / futuri).
    broker_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    broker_object_id = models.PositiveIntegerField(null=True, blank=True)
    broker = GenericForeignKey("broker_content_type", "broker_object_id")

    click_id = models.CharField(
        "Click id (affclickid)", max_length=64, unique=True, db_index=True)
    broker_lead_id = models.CharField(
        "Id lead broker", max_length=128, blank=True, db_index=True)

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

    @property
    def broker_name(self) -> str:
        b = self.broker
        return b.name if b else ""

    @classmethod
    def for_broker(cls, broker):
        ct = ContentType.objects.get_for_model(type(broker))
        return cls.objects.filter(broker_content_type=ct,
                                  broker_object_id=broker.pk)

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
    broker_label = models.CharField(max_length=120, blank=True)
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
