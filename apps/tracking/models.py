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
