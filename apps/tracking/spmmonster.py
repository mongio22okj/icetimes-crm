"""Client API SPM Monster (Hypernet HTN-AFF-SDK).

Endpoint unico (push + pull): /api/external/integration/lead
Auth: header x-api-key.
  Push  → POST  body {affc, bxc, vtc, profile{...}, ip, funnel, landingURL,
                geo, lang, landingLang, subId}
          risposta {success, redirectUrl, leadId}
  Pull  → GET   ?from=&to=  → {count, rows:[{id, registration{status}, ...}]}
`subId` = il NOSTRO click_id, che torna nella pull per agganciare gli stati.
"""
import json
import secrets
import urllib.error
import urllib.parse
import urllib.request

_PATH = "/api/external/integration/lead"
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")
_PULL_FMT = "%Y-%m-%dT%H:%M:%S.000Z"


class SpmError(Exception):
    """Errore di comunicazione o di rifiuto lato SPM Monster."""


def _request(broker, method, payload=None, params=None, timeout=30):
    url = broker.base_url.rstrip("/") + _PATH
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "x-api-key": broker.api_key,
        "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SpmError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SpmError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SpmError("timeout della richiesta") from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise SpmError(f"JSON non valido: {body[:200]}") from exc


def build_push_payload(broker, lead):
    geo = (lead.country or "IT").upper()
    lang = (lead.country or "IT").lower()
    return {
        "affc": broker.affc,
        "bxc": broker.bxc,
        "vtc": broker.vtc,
        "profile": {
            "firstName": lead.firstname,
            "lastName": lead.lastname,
            "email": lead.email,
            "password": secrets.token_urlsafe(9) + "A1",
            "phone": (lead.phone or "").lstrip("+"),  # SPM vuole il telefono senza +
        },
        "ip": lead.ip or "8.8.8.8",
        "funnel": broker.funnel or broker.name,
        "landingURL": broker.base_url,
        "geo": geo,
        "lang": lang,
        "landingLang": lang,
        # subId = il nostro click_id: torna nella pull per agganciare lo stato.
        "subId": lead.click_id,
    }


def push_lead(broker, lead):
    """POST del lead. Ritorna la risposta JSON (success/redirectUrl/leadId)."""
    return _request(broker, "POST", payload=build_push_payload(broker, lead))


def pull_leads(broker, dt_from, dt_to):
    """GET stati nel range. Ritorna la lista `rows`."""
    resp = _request(broker, "GET", params={
        "from": dt_from.strftime(_PULL_FMT),
        "to": dt_to.strftime(_PULL_FMT),
    })
    if isinstance(resp, dict):
        return resp.get("rows") or []
    return resp if isinstance(resp, list) else []


def extract_broker_lead_id(response):
    if isinstance(response, dict):
        return str(response.get("leadId") or response.get("id") or "")[:128]
    return ""


def extract_login_url(response):
    if isinstance(response, dict):
        return response.get("redirectUrl") or response.get("loginURL") or ""
    return ""
