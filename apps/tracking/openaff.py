"""Client API OpenAFF (API v2.1).

PUSH (registrazione lead): GET {API_domain}/api  — parametri in query string.
  Obbligatori: first_name, last_name, email, password (8-12 char, num+maiusc/
  minusc → generata da noi), phonecc (+xx), phone (senza prefisso), country
  (ISO2), user_ip (SOLO IPv4), aff_sub3 (=funnel), aff_id, offer_id (SEMPRE
  1737), referer. Header obbligatori: User-Agent, Accept-Language.
  Il NOSTRO click_id va in aff_sub → torna nella pull per agganciare lo stato.
  Risposta OK: {redirect (=autologin), lead_id, minimal_deposit, success:true}
  Errore: {success:false, errors:{campo:[msg]}}

PULL (stati): GET https://tracker.openaff.com/api/get_client_conversions
  header Authorization: Bearer <token>. Righe {id, ts, click_id, aff_sub..5,
  lead_status, conversion_type, cost}. FTD = conversion_type == "Conversion".
"""
import ipaddress
import re
import secrets
import string
import urllib.error
import urllib.parse
import urllib.request

_PUSH_PATH = "/api"
_PULL_URL = "https://tracker.openaff.com/api/get_client_conversions"
_OFFER_ID = "1737"  # fisso per contratto: cambiarlo dà errore
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")

# country ISO2 → prefisso telefonico (con +). Copre i geo che usiamo.
_COUNTRY_CC = {
    "IT": "+39", "ES": "+34", "DE": "+49", "SE": "+46", "GB": "+44",
    "UK": "+44", "IE": "+353", "FR": "+33", "PT": "+351", "AT": "+43",
    "CH": "+41", "NL": "+31", "BE": "+32", "DK": "+45", "NO": "+47",
    "FI": "+358", "PL": "+48", "CZ": "+420", "GR": "+30", "RO": "+40",
}
# country ISO2 → lingua ISO 639-1 (per Accept-Language). SE→sv (non "se").
_COUNTRY_LANG = {
    "IT": "it", "ES": "es", "DE": "de", "SE": "sv", "GB": "en", "UK": "en",
    "IE": "en", "FR": "fr", "PT": "pt", "AT": "de", "CH": "de", "NL": "nl",
    "BE": "nl", "DK": "da", "NO": "no", "FI": "fi", "GR": "el",
}


class OpenAffError(Exception):
    """Errore di comunicazione con OpenAFF."""


def _gen_password() -> str:
    """Password valida OpenAFF: 8-12 char, con numeri + maiuscole + minuscole."""
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(8))
    # Garantisce almeno una maiuscola, una minuscola e una cifra.
    return "A" + secrets.choice(string.ascii_lowercase) + \
        secrets.choice(string.digits) + core  # 11 char


def _ipv4(ip) -> str:
    """OpenAFF accetta SOLO IPv4. Se il lead non ne ha uno valido, fallback."""
    try:
        if ip and isinstance(ipaddress.ip_address(ip), ipaddress.IPv4Address):
            return str(ip)
    except ValueError:
        pass
    return "8.8.8.8"


def _split_phone(phone, phonecc):
    """Ritorna il telefono senza prefisso internazionale.
    Es. ('+34612345678', '+34') → '612345678'."""
    digits = re.sub(r"\D", "", phone or "")
    cc = phonecc.lstrip("+")
    if cc and digits.startswith(cc) and len(digits) > len(cc):
        return digits[len(cc):]
    # anche col doppio zero: 0034...
    if digits.startswith("00" + cc):
        return digits[len(cc) + 2:]
    return digits


def _referer(broker) -> str:
    slug = getattr(broker, "landing_slug", "") or ""
    if slug:
        return f"https://icetimes.it/lp/{slug}/"
    return broker.base_url


def build_push_params(broker, lead):
    geo = (lead.country or "IT").upper()
    phonecc = _COUNTRY_CC.get(geo, "+39")
    return {
        "first_name": lead.firstname or "",
        "last_name": lead.lastname or "",
        "email": lead.email or "",
        "password": _gen_password(),
        "phonecc": phonecc,
        "phone": _split_phone(lead.phone, phonecc),
        "country": geo,
        "user_ip": _ipv4(lead.ip),
        "aff_sub": lead.click_id,     # NOSTRO click_id → aggancio in pull
        "aff_sub3": broker.funnel or broker.name,   # funnel (obbligatorio)
        "aff_id": broker.aff_id,
        "offer_id": (broker.offer_id or _OFFER_ID),
        "referer": _referer(broker),
    }


def push_lead(broker, lead):
    """GET {base_url}{api_path or '/api'}?<params>. Ritorna la risposta JSON."""
    import json
    params = build_push_params(broker, lead)
    geo = (lead.country or "IT").upper()
    lang = _COUNTRY_LANG.get(geo, geo.lower())
    path = (getattr(broker, "api_path", "") or "").strip() or _PUSH_PATH
    url = broker.base_url.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": _BROWSER_UA,
        "Accept-Language": lang,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise OpenAffError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OpenAffError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenAffError("timeout della richiesta") from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise OpenAffError(f"JSON non valido: {body[:200]}") from exc


def pull_conversions(broker, date=None, all_statuses=True):
    """GET get_client_conversions (Bearer token) su broker.pull_url --
    deployment diversi (EPCERA, ecc.) hanno cabinet su domini diversi.
    Ritorna la lista `data`."""
    import json
    params = {}
    if date:
        params["date"] = date
    if all_statuses:
        params["all_statuses"] = "1"
    base = getattr(broker, "pull_url", "") or _PULL_URL
    url = base + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, method="GET", headers={
        "Authorization": f"Bearer {broker.token}",
        "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise OpenAffError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OpenAffError(f"non raggiungibile: {exc.reason}") from exc
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        # Token invalido → OpenAFF ritorna una pagina HTML, non JSON.
        raise OpenAffError(f"risposta non JSON (token?): {body[:120]}") from exc
    return data.get("data") or [] if isinstance(data, dict) else []


def extract_broker_lead_id(response):
    if isinstance(response, dict):
        return str(response.get("lead_id") or response.get("id") or "")[:128]
    return ""


def extract_login_url(response):
    if isinstance(response, dict):
        return response.get("redirect") or ""
    return ""
