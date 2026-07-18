"""Client API CPAForge (cpfrg-api.com).

Auth: header `Api-Key: <key>` su OGNI richiesta. ⚠️ Richiede IP whitelisting
lato CPAForge (il nostro IP server dev'essere autorizzato prima dell'uso).

PUSH (registrazione lead): POST {base}/api/v2/leads (form-urlencoded)
  campi: email, firstName, lastName, password (generata), ip, phone,
  areaCode (dial code paese), custom1 (= NOSTRO click_id → aggancio),
  comment (= funnel), offerName (opzionale), locale.
  OK: HTTP 200/201, details.leadRequest.ID (id univoco case-sensitive) +
  details.redirect.url (autologin). Errore: httpCode != 200 con `message`.

PULL (stati): GET {base}/api/v2/leads?fromDate=...&toDate=... (Api-Key)
  Risposta {items:[{leadRequestIDEncoded, custom1, saleStatus, hasFTD,
  customerID, countryCode, ...}]}. Aggancio per custom1 (= nostro click_id)
  o leadRequestIDEncoded (= broker_lead_id). FTD = hasFTD == 1.
"""
import json
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request

_LEADS_PATH = "/api/v2/leads"
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")

# Prefissi internazionali per separare areaCode dal numero nazionale.
_DIAL_CODES = {
    "IT": "39", "ES": "34", "DE": "49", "FR": "33", "GB": "44", "SE": "46",
    "AT": "43", "CH": "41", "NL": "31", "BE": "32", "PT": "351", "PL": "48",
    "NO": "47", "FI": "358", "DK": "45", "IE": "353", "CZ": "420", "GR": "30",
}

_LOCALES = {
    "IT": "it_IT", "ES": "es_ES", "DE": "de_DE", "FR": "fr_FR", "GB": "en_GB",
    "SE": "sv_SE", "AT": "de_AT", "CH": "de_CH", "NL": "nl_NL", "PT": "pt_PT",
    "PL": "pl_PL", "GR": "el_GR",
}


class CpaForgeError(Exception):
    """Errore di comunicazione con CPAForge."""


def _gen_password():
    """Password valida per CPAForge: max 12 caratteri, con maiuscola,
    minuscola e cifra garantite (loro validano lunghezza e complessità)."""
    rest = "".join(secrets.choice(string.ascii_letters + string.digits)
                   for _ in range(7))
    return "Aa1" + rest  # 10 char: A (upper), a (lower), 1 (digit) + 7


def _headers(broker):
    return {
        "Api-Key": broker.key,
        "Accept": "application/json",
        "User-Agent": _BROWSER_UA,
    }


def _split_phone(lead):
    """Ritorna (areaCode, phone_nazionale) a partire dal telefono del lead."""
    geo = (lead.country or "").upper()
    dial = _DIAL_CODES.get(geo, "")
    digits = "".join(ch for ch in str(lead.phone or "") if ch.isdigit())
    if dial and digits.startswith(dial):
        return dial, digits[len(dial):]
    return dial, digits


def build_push_data(broker, lead):
    geo = (lead.country or "IT").upper()
    area, phone = _split_phone(lead)
    data = {
        "email": lead.email or "",
        "firstName": (lead.firstname or "").strip() or "Lead",
        "lastName": (lead.lastname or "").strip() or "Lead",
        "password": _gen_password(),
        "ip": lead.ip or "",
        "phone": phone,
        "custom1": lead.click_id,   # NOSTRO id → aggancio nella pull
        "comment": broker.funnel or broker.name,
        "locale": _LOCALES.get(geo, "en_US"),
    }
    if area:
        data["areaCode"] = area
    if getattr(broker, "offer_name", "").strip():
        data["offerName"] = broker.offer_name.strip()
    return data


def push_lead(broker, lead):
    """POST del lead. Ritorna il JSON con chiave extra '_http' = status code."""
    url = broker.base_url.rstrip("/") + _LEADS_PATH
    body = urllib.parse.urlencode(build_push_data(broker, lead)).encode("utf-8")
    headers = _headers(broker)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise CpaForgeError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CpaForgeError("timeout della richiesta") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CpaForgeError(f"JSON non valido (HTTP {code}): {raw[:150]}") from exc
    if not isinstance(obj, dict):
        obj = {"_raw": obj}
    obj["_http"] = code
    return obj


def extract_lead_request_id(resp):
    """Estrae details.leadRequest.ID (id univoco case-sensitive)."""
    details = resp.get("details") if isinstance(resp, dict) else None
    if isinstance(details, dict):
        lr = details.get("leadRequest")
        if isinstance(lr, dict) and lr.get("ID"):
            return str(lr["ID"])
    return ""


def extract_login_url(resp):
    """Estrae details.redirect.url (autologin)."""
    details = resp.get("details") if isinstance(resp, dict) else None
    if isinstance(details, dict):
        red = details.get("redirect")
        if isinstance(red, dict) and red.get("url"):
            return str(red["url"])
    return ""


def pull_leads(broker, date_start=None, date_end=None):
    """GET /api/v2/leads nel range date. Ritorna la lista `items`.
    date_start/date_end nel formato 'YYYY-MM-DD HH:mm:ss'."""
    params = []
    if date_start:
        params.append(("fromDate", date_start))
    if date_end:
        params.append(("toDate", date_end))
    params.append(("itemsPerPage", "1000"))
    url = broker.base_url.rstrip("/") + _LEADS_PATH + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers=_headers(broker))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise CpaForgeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CpaForgeError(f"non raggiungibile: {exc.reason}") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CpaForgeError(f"risposta non JSON (key/whitelist?): {raw[:120]}") from exc
    if isinstance(obj, dict):
        return obj.get("items") or []
    return obj if isinstance(obj, list) else []


def is_deposit(row):
    """FTD CPAForge: campo hasFTD == 1 (o '1')."""
    return str(row.get("hasFTD") or "").strip() in ("1", "true", "True")
