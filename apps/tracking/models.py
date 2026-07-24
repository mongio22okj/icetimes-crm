import re
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
    extra_params = models.JSONField(
        "Parametri extra (JSON)", default=dict, blank=True,
        help_text='Parametri aggiuntivi inviati nel push, specifici del broker. '
                  'Es. {"MPC_7": "LIVE", "MPC_8": "59704"}. Vuoto = nessuno.')

    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Nome funnel inviato nel campo 'so'. Se vuoto usa il nome.")
    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing pubblica (visitor-facing). "
                  "Il nome interno del broker resta invariato nel CRM.")
    note = models.CharField(
        "Note", max_length=255, blank=True,
        help_text="Nota interna / nome alternativo del broker.")
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing di QUESTO broker. Se valorizzato, "
                  "/lp/<slug>/ mostra questo invece del form standard. Deve "
                  "contenere un <form method='POST' action='/lp/<slug>/'> con i "
                  "campi: firstname, lastname, email, phone, country.")

    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Se attivo, la pull aggancia i lead anche per email/telefono "
                  "(oltre a click_id/id). Da usare solo per broker che NON "
                  "restituiscono il nostro click_id nella pull (es. Link 10).")
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

    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Solo etichetta nostra: IREV NON riceve il funnel nel push "
                  "(lo decide dall'offer_id). Serve per riferimento/report.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing pubblica (visitor-facing). "
                  "Il nome interno del broker resta invariato nel CRM.")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing di QUESTO broker. Se valorizzato, "
                  "/lp/<slug>/ mostra questo invece del form standard. Deve "
                  "contenere un <form method='POST' action='/lp/<slug>/'> con i "
                  "campi: firstname, lastname, email, phone, country.")

    api_path = models.CharField(
        "API path (override)", max_length=120, blank=True,
        help_text="Path push/pull se diverso dal default. Vuoto = /affiliates/v2/leads. "
                  "Es. /api/affiliates/v2/leads")
    extra_params = models.JSONField(
        "Parametri extra (JSON)", default=dict, blank=True,
        help_text='Campi extra nel push, es. {"aff_sub3": "Eterna Immediata"}. Vuoto = nessuno.')
    use_pull = models.BooleanField(
        "Aggiorna stati via PULL", default=False,
        help_text="Se attivo, gli stati/FTD arrivano via pull get-leads (goal FTD). "
                  "Se OFF (default) lo stato arriva via postback. Tenere OFF sui broker esistenti.")
    is_active = models.BooleanField("Attivo", default=True)
    dedup_since = models.DateTimeField(
        "Antifrode da", null=True, blank=True,
        help_text="Se valorizzato, il controllo duplicati considera solo i lead "
                  "creati da questa data in poi. Utile al cambio broker/piattaforma: "
                  "chi si era iscritto PRIMA non blocca le nuove registrazioni.")
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
        return self.base_url.rstrip("/") + "/affiliates/v2/leads"

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


class SpmMonsterBroker(models.Model):
    """Configurazione API di un broker SPM Monster (Hypernet HTN-AFF-SDK).

    Endpoint unico {base_url}/api/external/integration/lead (auth x-api-key):
      push → POST (affc/bxc/vtc + profilo + subId=click_id)
      pull → GET ?from=&to= (stati). Lo stato si legge via PULL (sync).
    """

    kind = "spmmonster"
    kind_label = "SPM Monster"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField("Base URL", help_text="Es. https://spmteamone.it.com")
    api_key = models.CharField("x-api-key", max_length=255)
    affc = models.CharField("affc (affiliate code)", max_length=64)
    bxc = models.CharField("bxc (box code)", max_length=64)
    vtc = models.CharField("vtc (vertical code)", max_length=64)

    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Nome funnel inviato nel push. Se vuoto usa il nome.")
    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing pubblica (visitor-facing). "
                  "Il nome interno del broker resta invariato nel CRM.")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing di QUESTO broker. Se valorizzato, "
                  "/lp/<slug>/ mostra questo invece del form standard. Deve "
                  "contenere un <form method='POST' action='/lp/<slug>/'> con i "
                  "campi: firstname, lastname, email, phone, country.")

    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Se attivo, la pull aggancia i lead anche per email/telefono "
                  "(oltre a click_id/id). Attivalo solo se per questo broker "
                  "non riusciamo a leggere gli status nel modo normale.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker SPM Monster"
        verbose_name_plural = "Broker SPM Monster"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/external/integration/lead"

    def push(self, lead):
        from . import spmmonster
        try:
            resp = spmmonster.push_lead(self, lead) or {}
            if not resp.get("success"):
                detail = resp.get("error") or resp.get("message") or "push non riuscito"
                return _push_result(False, resp, error=str(detail)[:255])
            return _push_result(
                True, resp,
                broker_lead_id=spmmonster.extract_broker_lead_id(resp),
                login_url=spmmonster.extract_login_url(resp))
        except spmmonster.SpmError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class TYourAdsBroker(models.Model):
    """Broker TYourAds (tyourads-api.com). Push POST /api/v2/leads (header
    Api-Key); auto-login da details.redirect.url. Nessun pull noto: gli stati
    arrivano solo via postback se il broker lo supporta."""

    kind = "tyourads"
    kind_label = "TYourAds"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL", default="https://tyourads-api.com",
        help_text="Es. https://tyourads-api.com")
    api_key = models.CharField("Api-Key", max_length=255)
    offer_name = models.CharField(
        "offerName", max_length=160, blank=True,
        help_text='Es. "Bitcoin Bank". Se vuoto usa il nome del broker.')
    offer_website = models.CharField("offerWebsite", max_length=200, blank=True)

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing pubblica (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Deve contenere un <form "
                  "method='POST' action='/lp/<slug>/'> con i campi: firstname, "
                  "lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancia i lead anche per email/telefono nella pull/postback.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker TYourAds"
        verbose_name_plural = "Broker TYourAds"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def push(self, lead):
        from . import tyourads
        try:
            resp = tyourads.push_lead(self, lead) or {}
            url = tyourads.extract_login_url(resp)
            if url:
                return _push_result(
                    True, resp,
                    broker_lead_id=tyourads.extract_broker_lead_id(resp),
                    login_url=url)
            errs = resp.get("errors") or []
            detail = ((errs[0].get("message")
                       if errs and isinstance(errs[0], dict) else None)
                      or resp.get("message") or "push non riuscito")
            return _push_result(False, resp, error=str(detail)[:255])
        except tyourads.TYourAdsError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class GalassiaBroker(models.Model):
    """Broker tipo 'Galassia' (CRM /api/v3, es. elnopy.crypto-galassia.com).
    Push POST /api/v3/integration?api_token (auto-login da 'autologin');
    pull GET /api/v3/get-leads (status + acq=1 -> FTD); postback via click_id."""

    kind = "galassia"
    kind_label = "Galassia"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL", help_text="Es. https://elnopy.crypto-galassia.com")
    api_token = models.CharField("api_token", max_length=255)
    link_id = models.CharField("link_id", max_length=40)
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato come 'funnel'. Se vuoto usa il nome del broker.")
    source = models.CharField(
        "Source", max_length=120, blank=True,
        help_text="Inviato come 'source' (es. facebook).")
    country = models.CharField(
        "Country default", max_length=8, blank=True, default="IT",
        help_text="ISO 3166-1 alpha-2. Se il lead non ha country, usa questo.")
    language = models.CharField(
        "Language", max_length=8, blank=True, default="it",
        help_text="ISO 639-1 inviato come 'language'.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker Galassia"
        verbose_name_plural = "Broker Galassia"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def push(self, lead):
        from . import galassia
        try:
            resp = galassia.push_lead(self, lead) or {}
            if resp.get("success"):
                return _push_result(
                    True, resp,
                    broker_lead_id=galassia.extract_broker_lead_id(resp),
                    login_url=galassia.extract_login_url(resp))
            detail = resp.get("message") or "push non riuscito"
            return _push_result(False, resp, error=str(detail)[:255])
        except galassia.GalassiaError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class OpenAffBroker(models.Model):
    """Broker tipo 'OpenAFF' (API v2.1) -- famiglia white-label con piu'
    deployment (OpenAFF, EPCERA, ...): stesso formato ma dominio push/pull e
    path push possono differire per deployment, quindi configurabili per-broker
    (stesso principio di IrevBroker.api_path).
    Push GET {base_url}{api_path or '/api'} (params in URL, offer_id sempre
    1737; auto-login da 'redirect'); pull GET {pull_url} (Bearer token) →
    FTD = conversion_type == 'Conversion'. Aggancio per aff_sub (= nostro
    click_id) o lead_id."""

    kind = "openaff"
    kind_label = "OpenAFF"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "API domain", help_text="URL di invio lead dato dal manager. Es. http://vip.kofoboo.com")
    api_path = models.CharField(
        "Path push", max_length=60, blank=True,
        help_text="Path dell'endpoint di invio lead. Vuoto = '/api' (default "
                  "OpenAFF). Alcuni deployment (es. EPCERA) usano '/tracker'.")
    pull_url = models.URLField(
        "Pull cabinet URL", max_length=255,
        default="https://tracker.openaff.com/api/get_client_conversions",
        help_text="Endpoint get_client_conversions per leggere gli stati. Puo' "
                  "essere un dominio diverso da base_url (es. cabinet.epcera.com).")
    token = models.CharField(
        "Token PULL (Bearer)", max_length=1024,
        help_text="Token dal pannello (tracker.openaff.com/profile#tokens) per leggere gli stati.")
    aff_id = models.CharField("aff_id", max_length=64, help_text="Affiliate ID OpenAFF.")
    offer_id = models.CharField(
        "offer_id", max_length=32, default="1737",
        help_text="SEMPRE 1737 (cambiarlo dà errore).")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato come aff_sub3. Se vuoto usa il nome del broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker OpenAFF"
        verbose_name_plural = "Broker OpenAFF"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api"

    def push(self, lead):
        from . import openaff
        try:
            resp = openaff.push_lead(self, lead) or {}
            if resp.get("success"):
                return _push_result(
                    True, resp,
                    broker_lead_id=openaff.extract_broker_lead_id(resp),
                    login_url=openaff.extract_login_url(resp))
            errs = resp.get("errors") or {}
            if isinstance(errs, dict) and errs:
                first = next(iter(errs.values()))
                detail = (first[0] if isinstance(first, list) and first else str(first))
            else:
                detail = resp.get("message") or "push non riuscito"
            return _push_result(False, resp, error=str(detail)[:255])
        except openaff.OpenAffError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class GlobalTradeBroker(models.Model):
    """Broker tipo 'GlobalTrade' (crm.globaltrade-company.live).
    Push POST {base_url}/api/leads (JSON) → success = 'status', auto-login da
    'link_auto_login', id = 'lead_id'. Pull GET {base_url}/api/web-master/leads
    (Bearer token) per gli stati/FTD (formato risposta non documentato →
    aggancio best-effort)."""

    kind = "globaltrade"
    kind_label = "GlobalTrade"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL", default="https://crm.globaltrade-company.live",
        help_text="Dominio CRM. Push=/api/leads, pull=/api/web-master/leads.")
    token = models.CharField(
        "Token PULL (Bearer)", max_length=1024, blank=True,
        help_text="Token JWT del pannello per leggere gli stati (pull).")
    user_id = models.CharField(
        "user_id", max_length=64,
        help_text="ID web-master GlobalTrade (es. 276).")
    source = models.CharField(
        "source", max_length=120, blank=True,
        help_text="Sorgente inviata al broker (es. Adverterra).")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato come landing_name. Se vuoto usa il nome del broker.")
    landing_domain = models.CharField(
        "Dominio landing", max_length=120, default="goicetimes.com",
        help_text="Inviato come 'landing' (dominio dove gira la landing).")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker GlobalTrade"
        verbose_name_plural = "Broker GlobalTrade"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/leads"

    def push(self, lead):
        from . import globaltrade
        try:
            resp = globaltrade.push_lead(self, lead) or {}
            if resp.get("status"):
                return _push_result(
                    True, resp,
                    broker_lead_id=globaltrade.extract_broker_lead_id(resp),
                    login_url=globaltrade.extract_login_url(resp))
            detail = (resp.get("message") or resp.get("error")
                      or resp.get("errors") or "push non riuscito")
            return _push_result(False, resp, error=str(detail)[:255])
        except globaltrade.GlobalTradeError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class OneCryptBroker(models.Model):
    """Broker tipo 'OneCrypt' (cpa.tl / api.onecrypt.link).
    Push POST /api/lead/send (form, return_409_if_broker_declined=true) →
    success HTTP 200 {id, autologin_url}; rifiuto HTTP 409 {errmsg}. Pull GET
    /api/lead/feed (aggancio per id2 = nostro click_id). FTD = status
    'confirmed'/'confirmed_compensation'."""

    kind = "onecrypt"
    kind_label = "OneCrypt"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL API", default="http://api.onecrypt.link",
        help_text="Dominio API. Push=/api/lead/send, pull=/api/lead/feed.")
    key = models.CharField(
        "API key", max_length=255,
        help_text="Chiave di accesso API (profilo onecrypt.link/u/profile).")
    web_id = models.CharField(
        "Webmaster ID (web_id)", max_length=64, blank=True,
        help_text="ID affiliato/webmaster (es. 100790).")
    offer_id = models.CharField(
        "offer_id", max_length=32,
        help_text="ID offerta nel sistema OneCrypt (per geo).")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato nel campo 'comments'. Se vuoto usa il nome broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker OneCrypt"
        verbose_name_plural = "Broker OneCrypt"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/lead/send"

    def push(self, lead):
        from . import onecrypt
        try:
            resp = onecrypt.push_lead(self, lead) or {}
            ok = (resp.get("_http") == 200 and resp.get("id")
                  and not resp.get("error"))
            if ok:
                return _push_result(
                    True, resp,
                    broker_lead_id=str(resp.get("id") or "")[:128],
                    login_url=resp.get("autologin_url") or "")
            detail = (resp.get("error") or resp.get("errmsg")
                      or "push non riuscito")
            return _push_result(False, resp, error=str(detail)[:255])
        except onecrypt.OneCryptError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class CpaForgeBroker(models.Model):
    """Broker tipo 'CPAForge' (cpfrg-api.com). Auth header Api-Key (richiede IP
    whitelisting). Push POST /api/v2/leads (form) → success details.leadRequest.ID
    + details.redirect.url (autologin). Pull GET /api/v2/leads (aggancio per
    custom1 = nostro click_id, o leadRequestIDEncoded = broker_lead_id).
    FTD = hasFTD == 1."""

    kind = "cpaforge"
    kind_label = "CPAForge"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL API", default="https://cpfrg-api.com",
        help_text="Dominio API. Push=/api/v2/leads, pull=/api/v2/leads.")
    key = models.CharField(
        "API key (Api-Key)", max_length=255,
        help_text="Inviata nell'header Api-Key. Richiede IP whitelisting lato CPAForge.")
    offer_name = models.CharField(
        "Nome offerta (offerName)", max_length=120, blank=True,
        help_text="Inviato come offerName. Vuoto = instradamento automatico CPAForge.")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato nel campo 'comment'. Se vuoto usa il nome broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker CPAForge"
        verbose_name_plural = "Broker CPAForge"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/v2/leads"

    def push(self, lead):
        from . import cpaforge
        try:
            resp = cpaforge.push_lead(self, lead) or {}
            lead_req_id = cpaforge.extract_lead_request_id(resp)
            ok = (resp.get("_http") in (200, 201) and lead_req_id)
            if ok:
                return _push_result(
                    True, resp,
                    broker_lead_id=lead_req_id[:128],
                    login_url=cpaforge.extract_login_url(resp))
            msg = resp.get("message")
            if isinstance(msg, (list, tuple)):
                msg = msg[0] if msg else None
            detail = msg or f"push non riuscito (HTTP {resp.get('_http')})"
            return _push_result(False, resp, error=str(detail)[:255])
        except cpaforge.CpaForgeError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class AffinitraxBroker(models.Model):
    """Broker tipo 'Affinitrax' (affinitrax.com). Auth header X-API-Key.
    Push POST /api/v1/leads (JSON) -> success {lead_id, status, redirect_url}.
    Pull GET /api/v1/leads/{lead_id}: UN LEAD ALLA VOLTA, non esiste un
    endpoint bulk. Stati: in_progress -> relayed -> ftd (o rejected)."""

    kind = "affinitrax"
    kind_label = "Affinitrax"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL API", default="https://affinitrax.com",
        help_text="Dominio API. Push=/api/v1/leads, pull=/api/v1/leads/{id}.")
    api_key = models.CharField(
        "API key (X-API-Key)", max_length=255,
        help_text="Inviata nell'header X-API-Key.")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato nel campo 'sub1'. Se vuoto usa il nome broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker Affinitrax"
        verbose_name_plural = "Broker Affinitrax"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/v1/leads"

    def push(self, lead):
        from . import affinitrax
        try:
            resp = affinitrax.push_lead(self, lead) or {}
            lead_id = str(resp.get("lead_id") or "")
            ok = (resp.get("_http") == 200 and lead_id)
            if ok:
                return _push_result(True, resp, broker_lead_id=lead_id[:128],
                                    login_url=str(resp.get("redirect_url") or ""))
            detail = resp.get("error") or f"push non riuscito (HTTP {resp.get('_http')})"
            return _push_result(False, resp, error=str(detail)[:255])
        except affinitrax.AffinitraxError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


class LeadShakerBroker(models.Model):
    """Broker tipo 'Lead-Shaker' (crm.lead-shaker.live). Auth header
    Authorization: Bearer <token>. Push POST /api/leads (form-urlencoded).
    Pull GET /api/web-master/leads con BODY JSON {date_start, date_end}
    (si', una GET con body -- confermato funzionante). Risposta pull
    verificata: {success, data:{data:[...], total}, message}; i campi
    DENTRO ogni lead non sono documentati dal broker -- aggancio/status/FTD
    con le chiavi generiche gia' usate per gli altri broker, da verificare
    col payload vero dopo il primo test."""

    kind = "leadshaker"
    kind_label = "Lead-Shaker"

    name = models.CharField("Nome", max_length=120)
    base_url = models.URLField(
        "Base URL API", default="https://crm.lead-shaker.live",
        help_text="Dominio API. Push=/api/leads, pull=/api/web-master/leads.")
    token = models.CharField(
        "Token (Bearer)", max_length=2048,
        help_text="Inviato come header Authorization: Bearer <token>.")
    user_id = models.CharField(
        "User ID (nel loro sistema)", max_length=40,
        help_text="Il tuo ID assegnato da Lead-Shaker. Inviato come 'user_id'.")
    source = models.CharField(
        "Source (il tuo nickname da loro)", max_length=120,
        help_text="Inviato come 'source'. Es. 'Adverterra'.")
    funnel = models.CharField(
        "Funnel", max_length=120, blank=True,
        help_text="Inviato come 'landing_name'. Se vuoto usa il nome broker.")

    landing_slug = models.SlugField(
        "Slug landing", max_length=60, blank=True, null=True, unique=True,
        help_text="Landing pubblica: /lp/<slug>/.")
    landing_brand = models.CharField(
        "Brand landing", max_length=120, blank=True,
        help_text="Nome/logo mostrato sulla landing (visitor-facing).")
    note = models.CharField("Note", max_length=255, blank=True)
    landing_html = models.TextField(
        "HTML landing personalizzata", blank=True,
        help_text="HTML completo della landing. Form POST a /lp/<slug>/ con "
                  "campi: firstname, lastname, email, phone, country.")
    match_by_contact = models.BooleanField(
        "Aggancio per email/telefono", default=False,
        help_text="Aggancio extra per email/telefono nella pull, se serve.")
    is_active = models.BooleanField("Attivo", default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Broker Lead-Shaker"
        verbose_name_plural = "Broker Lead-Shaker"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def signup_url(self) -> str:
        return self.base_url.rstrip("/") + "/api/leads"

    def push(self, lead):
        from . import leadshaker
        try:
            resp = leadshaker.push_lead(self, lead) or {}
            lead_id = leadshaker.extract_broker_lead_id(resp)
            # Campo VERO confermato con un test reale (2026-07-23): la risposta
            # usa "status" (bool), non "success" -- {"status": false, "error":
            # "..."} sui rifiuti (es. "Offers not found", offerta non attiva
            # sull'account). Prima controllavamo "success" (assente -> None ->
            # veniva letto come riuscito per errore).
            ok = (resp.get("_http") in (200, 201) and resp.get("status") is True)
            if ok:
                return _push_result(True, resp, broker_lead_id=lead_id,
                                    login_url=leadshaker.extract_login_url(resp))
            detail = (resp.get("error") or resp.get("message")
                     or f"push non riuscito (HTTP {resp.get('_http')})")
            return _push_result(False, resp, error=str(detail)[:255])
        except leadshaker.LeadShakerError as exc:
            return _push_result(False, error=str(exc)[:255])
        except Exception as exc:  # noqa: BLE001
            return _push_result(False, error=f"{type(exc).__name__}: {exc}"[:255])


# Tipi di broker registrati: kind → modello. Per risolvere slug/landing e
# costruire elenchi unificati senza accoppiare il resto del codice.
BROKER_MODELS = (TrackboxBroker, IrevBroker, SpmMonsterBroker, TYourAdsBroker,
                 GalassiaBroker, OpenAffBroker, GlobalTradeBroker, OneCryptBroker,
                 CpaForgeBroker, AffinitraxBroker, LeadShakerBroker)


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


_KIND_MODELS = {m.kind: m for m in BROKER_MODELS}


import re as _re


def natural_sort_key(name):
    """Chiave di ordinamento 'naturale': i numeri nel nome contano per
    valore, non carattere-per-carattere (Link 9 prima di Link 10 prima di
    Link 22, non 10/22 prima di 9 come farebbe l'ordine alfabetico puro)."""
    return [int(chunk) if chunk.isdigit() else chunk.lower()
            for chunk in _re.split(r"(\d+)", name)]


def broker_by_kind(kind, pk):
    model = _KIND_MODELS.get(kind)
    if model is None:
        return None
    return model.objects.filter(pk=pk).first()


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
    # FTD gia' pagata all'utente (payout incassato). Viene sottratta dal
    # "Guadagno da incassare" nella dashboard e colorata AZZURRA nella tabella
    # Lead. Ha senso solo quando is_deposit=True.
    ftd_paid = models.BooleanField("FTD pagata", default=False, db_index=True)
    # Antifrode: lead riconosciuto come duplicato sullo STESSO broker.
    # Viene salvato nel CRM (riga rossa) ma NON inviato al broker.
    is_duplicate = models.BooleanField("Duplicato", default=False)
    duplicate_reason = models.CharField("Motivo duplicato", max_length=40, blank=True)
    # Fase interna (pipeline call-center), separata dallo `status` grezzo broker.
    STAGE_CHOICES = [
        ("nuovo", "Nuovo"),
        ("instant_call", "Instant call"),
        ("in_work", "In work"),
        ("no_answer", "Nessuna risposta"),
        ("callback", "Call back"),
        ("basso_potenziale", "Basso potenziale"),
        ("nessun_potenziale", "Nessun potenziale"),
        ("not_interested", "Nessun interesse"),
        ("ftd", "FTD"),
    ]
    stage = models.CharField("Fase", max_length=20, choices=STAGE_CHOICES,
                             default="nuovo", db_index=True)
    reject_reason = models.CharField("Motivo rifiuto", max_length=255, blank=True)
    note = models.CharField("Nota", max_length=255, blank=True)

    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    event_at = models.DateTimeField("Data evento", null=True, blank=True)
    # Ultima volta che la pull API ha agganciato (visto) questo lead.
    last_pull_at = models.DateTimeField("Ultimo agg. API", null=True, blank=True)
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


def status_to_stage(status):
    """Mappa l'esito-chiamata del broker (testo libero) sulla nostra fase.
    Ritorna la fase corrispondente o None se lo stato non e' riconosciuto.

    Molti broker (TrackBox) mandano gli stati in camelCase senza spazi
    ("NotInterested", "HungUp", "WrongInfo") o TUTTO-MAIUSCOLO ("NOTINTERESTED",
    "WRONGNUMBER"): inseriamo uno spazio ai confini minuscola->MAIUSCOLA (così
    combaciano con le diciture con spazio) e teniamo anche le varianti compatte
    per i casi tutto-maiuscolo."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(status or "")).strip().lower()
    if not s:
        return None
    if any(k in s for k in ("ftd", "deposit", "depositor", "deposited",
                            "sale", "converted", "convert", "first deposit",
                            "deposito", "real deposit")):
        return "ftd"
    if any(k in s for k in ("not interested", "notinterested", "not interest", "no interest",
                            "uninterested", "non interess", "no_interest", "rejected", "reject",
                            "do not call", "dnc", "invalid", "fake", "trash",
                            "junk", "duplicate", "not qualified", "notqualified", "unqualified",
                            "declined", "spam", "no money", "no_money",
                            "wrong info", "wronginfo", "wrong_info")):
        return "not_interested"
    if any(k in s for k in ("no potential", "nopotential", "no_potential", "nessun potenzial",
                            "not potential", "notpotential", "no value", "zero potential")):
        return "nessun_potenziale"
    if any(k in s for k in ("low potential", "lowpotential", "low_potential", "basso potenzial",
                            "low value", "low priority", "low quality")):
        return "basso_potenziale"
    if any(k in s for k in ("callback", "call back", "call-back", "recall",
                            "richiam", "ricontatt", "interested", "interessat",
                            "hot lead", "warm lead", "call again", "call later",
                            "follow up", "followup", "da richiamare")):
        return "callback"
    if any(k in s for k in ("instant call", "instantcall", "instant_call",
                            "instant-call", "live call")):
        return "instant_call"
    if any(k in s for k in ("in work", "inwork", "in_work", "working",
                            "in lavorazione", "in progress", "in-progress",
                            "processing", "assigned", "in process",
                            "under review")):
        return "in_work"
    if any(k in s for k in ("no answer", "noanswer", "no_answer", "not reachable",
                            "no response", "noresponse", "nessuna risposta",
                            "non rispon", "unreachable", "busy", "voicemail",
                            "wrong number", "wrongnumber", "wrong_number",
                            "hangup", "hang up", "hung up", "hungup",
                            "never answer", "neveranswer",
                            "answering machine", "answer machine",
                            "no pickup", "no pick up", "did not answer",
                            "not answered", "no reply")):
        return "no_answer"
    return None
