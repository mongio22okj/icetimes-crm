"""Client API OneCrypt (cpa.tl / api.onecrypt.link).

PUSH (registrazione lead): POST {base_url}/api/lead/send?return_409_if_broker_declined=true
  body form-urlencoded: key, id (= NOSTRO click_id → torna come id2 nella feed),
  offer_id, web_id, name (nome+cognome), phone, email, country (ISO2),
  ip_address, user_agent, comments (=funnel), sub5=0.
  OK: HTTP 200 JSON {id, autologin_url?, payout?}. Rifiuto: HTTP 409 {errmsg}.
  Anche su 200 può esserci "error" se non inviato all'advertiser.

PULL (stati): GET {base_url}/api/lead/feed?key=...&date[]=from&date[]=to&date_to_with=true
  Risposta {count, total, leads:[{id, id2, status, status_code, comment, ...}]}.
  Aggancio per id2 (= nostro click_id) o id (= broker_lead_id).
  FTD = status "confirmed"/"confirmed_compensation" (status_code 10/15).
  L'esito-chiamata reale sta in `comment`.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_PUSH_PATH = "/api/lead/send"
_FEED_PATH = "/api/lead/feed"
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class OneCryptError(Exception):
    """Errore di comunicazione con OneCrypt."""


def _full_name(lead):
    fn = (lead.firstname or "").strip()
    ln = (lead.lastname or "").strip()
    return (fn + " " + ln).strip() or fn or ln


def build_push_data(broker, lead):
    geo = (lead.country or "IT").upper()
    return {
        "key": broker.key,
        "id": lead.click_id,  # NOSTRO id → id2 nella feed (aggancio)
        "offer_id": broker.offer_id,
        "web_id": broker.web_id or "",
        "name": _full_name(lead),
        "phone": lead.phone or "",
        "email": lead.email or "",
        "country": geo,
        "ip_address": lead.ip or "",
        "user_agent": _BROWSER_UA,
        "comments": broker.funnel or broker.name,
        "sub5": "0",
    }


def push_lead(broker, lead):
    """POST del lead. Ritorna il JSON con chiave extra '_http' = status code."""
    url = (broker.base_url.rstrip("/") + _PUSH_PATH
           + "?return_409_if_broker_declined=true")
    body = urllib.parse.urlencode(build_push_data(broker, lead)).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # 409 = broker declined (con errmsg); leggiamo comunque il body.
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise OneCryptError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OneCryptError("timeout della richiesta") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise OneCryptError(f"JSON non valido (HTTP {code}): {raw[:150]}") from exc
    if not isinstance(obj, dict):
        obj = {"_raw": obj}
    obj["_http"] = code
    return obj


def pull_leads(broker, date_start=None, date_end=None):
    """GET /api/lead/feed nel range date. Ritorna la lista `leads`."""
    params = [("key", broker.key)]
    if date_start and date_end:
        params += [("date[]", date_start), ("date[]", date_end),
                   ("date_to_with", "true")]
    elif date_start:
        params.append(("date", date_start))
    url = broker.base_url.rstrip("/") + _FEED_PATH + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="GET", headers={
        "Accept": "application/json", "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise OneCryptError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise OneCryptError(f"non raggiungibile: {exc.reason}") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise OneCryptError(f"risposta non JSON (key?): {raw[:120]}") from exc
    if isinstance(obj, dict):
        return obj.get("leads") or []
    return obj if isinstance(obj, list) else []


def is_deposit(row):
    """FTD OneCrypt: status confirmed/confirmed_compensation o status_code 10/15."""
    st = str(row.get("status") or "").strip().lower()
    return (st in ("confirmed", "confirmed_compensation")
            or str(row.get("status_code")) in ("10", "15"))
