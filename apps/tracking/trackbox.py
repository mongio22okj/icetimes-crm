"""Client API TrackBox (es. FINTECHGURUS / track.fintechgurus.org).

Implementa il PUSH del lead verso il broker:
    POST {base_url}/api/signup/procform
con header x-trackbox-username / x-trackbox-password / x-api-key (= push_key).

Niente chiamate "di test" partono da qui automaticamente: `push_lead` viene
invocato solo quando un lead reale viene inviato (azione staff o landing).
"""
import json
import secrets
import urllib.error
import urllib.request

# UA da browser: Cloudflare (davanti a molti broker) blocca "Python-urllib"
# con 403 (error 1010). Serve uno UA reale per passare il WAF.
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class TrackboxError(Exception):
    """Errore di comunicazione o di rifiuto lato TrackBox."""


def _request(broker, path, payload, api_key, timeout=25):
    url = broker.base_url.rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-trackbox-username": broker.username,
            "x-trackbox-password": broker.password,
            "x-api-key": api_key,
            "User-Agent": _BROWSER_UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise TrackboxError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise TrackboxError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise TrackboxError("timeout della richiesta") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise TrackboxError(f"JSON non valido: {body[:200]}") from exc

    # TrackBox segnala il rifiuto con status=False + errorMessage / data(str).
    if isinstance(data, dict) and data.get("status") is False:
        detail = (data.get("errorMessage")
                  or (data.get("data") if isinstance(data.get("data"), str) else None)
                  or data.get("error") or data.get("message")
                  or "errore sconosciuto")
        raise TrackboxError(f"{detail} (code {data.get('code', '?')})")
    return data


# Il codice paese NON sempre coincide col codice lingua per il campo "lg":
# SE (Svezia) -> SV (svedese, non "SE"=sami), GB/UK -> EN, DK -> DA, ecc.
_COUNTRY_LANG = {
    "SE": "SV", "GB": "EN", "UK": "EN", "IE": "EN", "DK": "DA",
    "AT": "DE", "CH": "DE", "BE": "NL", "GR": "EL",
}


def _lg_for(country):
    geo = (country or "IT").upper()
    return _COUNTRY_LANG.get(geo, geo)


def build_push_payload(broker, lead):
    """Costruisce il body del push dal broker + lead (senza inviare nulla)."""
    payload = {
        "ai": broker.ai,
        "ci": broker.ci or "1",
        "gi": broker.gi,
        "userip": lead.ip or "8.8.8.8",
        "firstname": lead.firstname,
        "lastname": lead.lastname,
        "email": lead.email,
        "phone": lead.phone,
        "password": secrets.token_urlsafe(10),
        # affclickid = il NOSTRO click_id: il broker lo rimanda nel postback
        # come lead_id → è la chiave di aggancio degli aggiornamenti di stato.
        "affclickid": lead.click_id,
        # so = nome funnel (visibile nei report broker).
        "so": broker.funnel or broker.name,
        "lg": _lg_for(lead.country),
    }
    # Parametri extra specifici del broker (es. SoftTrack: MPC_7/MPC_8).
    extra = getattr(broker, "extra_params", None)
    if isinstance(extra, dict):
        payload.update({str(k): v for k, v in extra.items()})
    return payload


def push_lead(broker, lead):
    """Invia il lead al broker. Ritorna la risposta JSON o solleva TrackboxError."""
    return _request(broker, "/api/signup/procform",
                    build_push_payload(broker, lead), broker.push_key)


# ── PULL (stati/depositi) ────────────────────────────────────────────────
PULL_LEADS = "2"
PULL_LEADS_AND_DEPOSITS = "3"
PULL_DEPOSITS = "4"
_PULL_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def pull_customers(broker, date_from, date_to,
                   pull_type=PULL_LEADS_AND_DEPOSITS, page=0, timeout=30):
    """Legge stati/depositi dal broker: POST /api/pull/customers (pull_key)."""
    payload = {
        "from": date_from.strftime(_PULL_DATE_FMT),
        "to": date_to.strftime(_PULL_DATE_FMT),
        "type": str(pull_type),
        "page": str(page),
    }
    return _request(broker, "/api/pull/customers", payload,
                    broker.pull_key, timeout=timeout)


def extract_rows(response):
    """Normalizza la risposta della pull in una lista di righe."""
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("customers", "leads", "rows", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
    return []


def extract_broker_lead_id(response):
    """Estrae l'id-lead ritornato dal broker dopo un push accettato.

    TrackBox annida in addonData.data: {id, customerId, uniqueid}. Preferiamo
    l'`id`/`customerId` numerico; teniamo `uniqueid` (hash) come fallback.
    """
    if not isinstance(response, dict):
        return ""
    addon = response.get("addonData") or {}
    containers = [response,
                  addon.get("data") if isinstance(addon, dict) else None,
                  response.get("data") if isinstance(response.get("data"), dict) else None]
    for c in containers:
        if isinstance(c, dict):
            for key in ("id", "customerId", "lead_id", "leadId", "uuid", "uniqueid"):
                if c.get(key):
                    return str(c[key])[:128]
    return ""


def extract_login_url(response):
    """URL di auto-login ritornato dal broker (loginURL o data stringa URL)."""
    if not isinstance(response, dict):
        return ""
    addon = response.get("addonData") or {}
    addon_data = addon.get("data") if isinstance(addon, dict) else {}
    addon_data = addon_data if isinstance(addon_data, dict) else {}
    top = response.get("data")
    return (addon_data.get("loginURL")
            or (top if isinstance(top, str) and top.startswith("http") else "")
            or "")
