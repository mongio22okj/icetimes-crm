"""Client API Affinitrax (affinitrax.com/docs/seller-api).

Auth: header `X-API-Key: <key>` su OGNI richiesta.

PUSH (registrazione lead): POST {base}/api/v1/leads (JSON, non form!)
  campi: email*, phone*, country* (ISO alpha-2), first_name, last_name, ip,
  click_id (= NOSTRO click_id -> aggancio), sub1/sub2/sub3.
  OK: HTTP 200 {lead_id, status, redirect_url}. Errore: HTTP 400+ {error}.

PULL (stato): GET {base}/api/v1/leads/{lead_id} -- UN LEAD ALLA VOLTA, non
  esiste un endpoint che restituisce una lista. Stessa risposta del push
  {lead_id, status, redirect_url}. Limite broker: 200 richieste/IP/minuto.
  Stati: in_progress -> relayed -> ftd (o rejected).
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_LEADS_PATH = "/api/v1/leads"


class AffinitraxError(Exception):
    """Errore di comunicazione con Affinitrax."""


def _headers(broker):
    return {
        "X-API-Key": broker.api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def build_push_payload(broker, lead):
    payload = {
        "email": lead.email or "",
        "phone": lead.phone or "",
        "country": (lead.country or "IT").upper(),
        "first_name": lead.firstname or "",
        "last_name": lead.lastname or "",
        "click_id": lead.click_id,
        "sub1": broker.funnel or broker.name,
    }
    if lead.ip:
        payload["ip"] = str(lead.ip)
    return payload


def _call(method, url, broker, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=_headers(broker))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise AffinitraxError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AffinitraxError("timeout della richiesta") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise AffinitraxError(f"JSON non valido (HTTP {code}): {raw[:150]}") from exc
    if not isinstance(obj, dict):
        obj = {"_raw": obj}
    obj["_http"] = code
    return obj


def push_lead(broker, lead):
    """POST del lead. Ritorna il JSON con chiave extra '_http' = status code."""
    url = broker.base_url.rstrip("/") + _LEADS_PATH
    return _call("POST", url, broker, build_push_payload(broker, lead))


def get_lead_status(broker, lead_id):
    """GET dello stato di UN lead. Ritorna il JSON con '_http'."""
    url = broker.base_url.rstrip("/") + _LEADS_PATH + "/" + urllib.parse.quote(str(lead_id), safe="")
    return _call("GET", url, broker)


def is_deposit(status):
    """FTD Affinitrax: status letterale 'ftd'."""
    return str(status or "").strip().lower() == "ftd"
