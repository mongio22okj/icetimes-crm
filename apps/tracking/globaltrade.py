"""Client API GlobalTrade (crm.globaltrade-company.live).

PUSH (registrazione lead): POST {base_url}/api/leads  — body JSON.
  Campi: email, full_name (nome+cognome), landing (dominio landing),
  country (ISO2), landing_name (=funnel), user_id, lang (it/de/en...),
  source, phone (con prefisso, SENZA +), ip, description.
  Header: Accept + Content-Type application/json (nessun auth sul push).
  Risposta OK: {status:true, external_id, link_auto_login, lead_id}
  → success = status ; autologin = link_auto_login ; id = lead_id.

PULL (stati): GET {base_url}/api/web-master/leads  header Authorization:
  Bearer <token>, body {date_start, date_end}. Il formato della risposta
  NON e' documentato → parsing best-effort (lista sotto data/leads/...).
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

_PUSH_PATH = "/api/leads"
_PULL_PATH = "/api/web-master/leads"
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")

# country ISO2 → prefisso telefonico (senza +, GlobalTrade lo vuole così).
_COUNTRY_CC = {
    "IT": "39", "ES": "34", "DE": "49", "SE": "46", "GB": "44", "UK": "44",
    "IE": "353", "FR": "33", "PT": "351", "AT": "43", "CH": "41", "NL": "31",
    "BE": "32", "DK": "45", "NO": "47", "FI": "358", "PL": "48", "CZ": "420",
    "GR": "30", "RO": "40",
}
# country ISO2 → lingua ISO 639-1. SE→sv (non "se").
_COUNTRY_LANG = {
    "IT": "it", "ES": "es", "DE": "de", "SE": "sv", "GB": "en", "UK": "en",
    "IE": "en", "FR": "fr", "PT": "pt", "AT": "de", "CH": "de", "NL": "nl",
    "BE": "nl", "DK": "da", "NO": "no", "FI": "fi", "GR": "el",
}


class GlobalTradeError(Exception):
    """Errore di comunicazione con GlobalTrade."""


def _phone_digits(phone, cc):
    """Telefono in sole cifre con prefisso internazionale, SENZA +.
    Es. ('+49 157 12345', '49') → '4915712345'."""
    d = re.sub(r"\D", "", phone or "")
    if not d:
        return d
    if cc and not d.startswith(cc):
        d = cc + d.lstrip("0")
    return d


def _full_name(lead):
    fn = (lead.firstname or "").strip()
    ln = (lead.lastname or "").strip()
    return (fn + " " + ln).strip() or fn or ln


def build_push_payload(broker, lead):
    geo = (lead.country or "DE").upper()
    cc = _COUNTRY_CC.get(geo, "")
    return {
        "email": lead.email or "",
        "full_name": _full_name(lead),
        "landing": broker.landing_domain or "goicetimes.com",
        "country": geo,
        "landing_name": broker.funnel or broker.name,
        "user_id": str(broker.user_id or ""),
        "lang": _COUNTRY_LANG.get(geo, geo.lower()),
        "source": broker.source or "",
        "phone": _phone_digits(lead.phone, cc),
        "ip": lead.ip or "",
        "description": broker.landing_brand or broker.funnel or "",
    }


def push_lead(broker, lead):
    """POST {base_url}/api/leads con body JSON. Ritorna la risposta JSON."""
    url = broker.base_url.rstrip("/") + _PUSH_PATH
    body = json.dumps(build_push_payload(broker, lead)).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise GlobalTradeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise GlobalTradeError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise GlobalTradeError("timeout della richiesta") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise GlobalTradeError(f"JSON non valido: {raw[:200]}") from exc


def pull_leads(broker, date_start=None, date_end=None, max_pages=50):
    """GET {base_url}/api/web-master/leads (Bearer). Ritorna la lista di righe.

    Risposta reale (2026-07-13): {success, data:{data:[...], current_page,
    total_pages, total}}. Ogni riga: {id, email, status:{id,name}, is_action,
    action_time, date}. Le righe sono annidate in data.data; gestiamo la
    paginazione via `page`."""
    base = broker.base_url.rstrip("/") + _PULL_PATH
    rows = []
    page = 1
    while page <= max_pages:
        params = {}
        if date_start:
            params["date_start"] = date_start
        if date_end:
            params["date_end"] = date_end
        if page > 1:
            params["page"] = page
        url = base + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, method="GET", headers={
            "Authorization": f"Bearer {broker.token}",
            "Accept": "application/json",
            "User-Agent": _BROWSER_UA,
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise GlobalTradeError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GlobalTradeError(f"non raggiungibile: {exc.reason}") from exc
        try:
            obj = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise GlobalTradeError(f"risposta non JSON (token?): {raw[:120]}") from exc
        d = obj.get("data") if isinstance(obj, dict) else obj
        if isinstance(d, dict):
            page_rows = d.get("data")
            if isinstance(page_rows, list):
                rows.extend(page_rows)
            total_pages = int(d.get("total_pages") or 1)
            if page >= total_pages:
                break
            page += 1
        elif isinstance(d, list):
            rows.extend(d)
            break
        else:
            break
    return rows


def extract_broker_lead_id(response):
    if isinstance(response, dict):
        return str(response.get("lead_id") or response.get("external_id") or "")[:128]
    return ""


def extract_login_url(response):
    if isinstance(response, dict):
        return response.get("link_auto_login") or response.get("redirect") or ""
    return ""
