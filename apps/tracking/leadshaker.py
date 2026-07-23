"""Client API Lead-Shaker (crm.lead-shaker.live).

Auth: header `Authorization: Bearer <token>`.

PUSH (registrazione lead): POST {base}/api/leads (form-urlencoded)
  campi: full_name, country, email, landing (URL della nostra landing),
  phone, user_id (il nostro ID nel loro sistema), ip, source (il nostro
  nickname da loro), keitaro_id (= NOSTRO click_id -> aggancio),
  description, landing_name.
  Risposta CONFERMATA con un test reale (2026-07-23): il campo e' "status"
  (bool), non "success". Rifiuto: {"status": false, "error": "..."} (es.
  "Offers not found" = offerta non attiva sull'account, da attivare col
  referente). Forma esatta di un successo ("status": true, ...) ancora da
  vedere -- extract_broker_lead_id() resta difensiva su piu' chiavi.

PULL (stati): GET {base}/api/web-master/leads con BODY JSON -- si', e'
  una GET con body: cosi' la documenta Lead-Shaker e cosi' risponde
  (verificato). Body {date_start, date_end} formato YYYY-MM-DD.
  Risposta confermata: {success, data:{data:[...], current_page,
  total_pages, total}, message}. ⚠️ I campi DENTRO ogni lead non sono
  documentati (lista sempre vuota finora, nessun lead reale pushato):
  l'aggancio/status/FTD usa le stesse chiavi generiche degli altri
  broker (_ID_KEYS/_STATUS_KEYS/_DEPOSIT_KEYS in sync.py) -- verificare
  col payload vero (payload['last_pull']) dopo il primo test reale e
  correggere qui se il loro nome-campo non e' tra quelli generici.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_PUSH_PATH = "/api/leads"
_PULL_PATH = "/api/web-master/leads"
# Il sito e' dietro Cloudflare: senza uno User-Agent da browser vero il bot
# protection lo respinge con "Error 1010: browser_signature_banned" (visto
# in produzione col primo test reale).
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class LeadShakerError(Exception):
    """Errore di comunicazione con Lead-Shaker."""


def _headers(broker, content_type):
    return {
        "Authorization": f"Bearer {broker.token}",
        "Content-Type": content_type,
        "Accept": "application/json",
        "User-Agent": _BROWSER_UA,
    }


def _call(method, url, broker, form_body=None, json_body=None):
    if form_body is not None:
        data = urllib.parse.urlencode(form_body).encode("utf-8")
        headers = _headers(broker, "application/x-www-form-urlencoded")
    elif json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers = _headers(broker, "application/json")
    else:
        data, headers = None, _headers(broker, "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise LeadShakerError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LeadShakerError("timeout della richiesta") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise LeadShakerError(f"JSON non valido (HTTP {code}): {raw[:150]}") from exc
    if not isinstance(obj, dict):
        obj = {"_raw": obj}
    obj["_http"] = code
    return obj


def build_push_payload(broker, lead):
    landing_url = (f"https://icetimes.it/lp/{broker.landing_slug}/"
                   if broker.landing_slug else "")
    return {
        "full_name": f"{lead.firstname or ''} {lead.lastname or ''}".strip(),
        "country": (lead.country or "IT").upper(),
        "email": lead.email or "",
        "landing": landing_url,
        "phone": lead.phone or "",
        "user_id": broker.user_id,
        "ip": lead.ip or "",
        "source": broker.source,
        "keitaro_id": lead.click_id,
        "description": "",
        "landing_name": broker.funnel or broker.name,
    }


def push_lead(broker, lead):
    url = broker.base_url.rstrip("/") + _PUSH_PATH
    return _call("POST", url, broker, form_body=build_push_payload(broker, lead))


def extract_login_url(resp):
    """Link autologin CONFERMATO con un test reale (2026-07-23): campo
    'link_auto_login' in cima alla risposta di successo."""
    if not isinstance(resp, dict):
        return ""
    for key in ("link_auto_login", "autologin", "redirect_url", "login_url"):
        v = resp.get(key)
        if v:
            return str(v)
    return ""


def extract_broker_lead_id(resp):
    """Formato NON documentato: proviamo le chiavi piu' comuni, sia in
    cima alla risposta sia dentro 'data' (come fa gia' la pull)."""
    if not isinstance(resp, dict):
        return ""
    data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
    for key in ("id", "lead_id", "uuid"):
        for src in (data, resp):
            v = src.get(key)
            if v:
                return str(v)[:128]
    return ""


def pull_leads(broker, date_start, date_end):
    """GET con BODY JSON (confermato funzionante). Ritorna la lista grezza
    dei lead da data.data (envelope verificato via chiamata di prova)."""
    url = broker.base_url.rstrip("/") + _PULL_PATH
    resp = _call("GET", url, broker,
                json_body={"date_start": date_start, "date_end": date_end})
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("data") or []
    if isinstance(data, list):
        return data
    return []
