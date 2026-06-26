"""Client API IREV (Lead Distribution Affiliate API v2).

Push del lead:
    POST {base_url}/api/affiliates/v2/leads
    header Authorization: <token>
Lo stato torna via POSTBACK (broker→noi), come TrackBox; la pull esiste
ma non è necessaria per gli stati base.
"""
import json
import urllib.error
import urllib.request

_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/124.0.0.0 Safari/537.36")


class IrevError(Exception):
    """Errore di comunicazione o di rifiuto lato IREV."""


def _request(broker, method, path, payload=None, timeout=30):
    url = broker.base_url.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": broker.token,
        "Content-Type": "application/json",
        "User-Agent": _BROWSER_UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise IrevError(_explain(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise IrevError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise IrevError("timeout della richiesta") from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise IrevError(f"JSON non valido: {body[:200]}") from exc


def _explain(code, detail):
    """Estrae un messaggio leggibile dagli errori IREV (formato MoleculerError)."""
    msg = detail[:300]
    try:
        d = json.loads(detail)
        inner = d.get("data") or {}
        msg = (inner.get("errorMessage") or d.get("message")
               or d.get("type") or msg)
    except (json.JSONDecodeError, AttributeError):
        pass
    return f"HTTP {code}: {msg}"


def build_push_payload(broker, lead):
    return {
        "ip": lead.ip or "8.8.8.8",
        "country_code": (lead.country or "IT").upper(),
        "first_name": lead.firstname,
        "last_name": lead.lastname,
        "email": lead.email,
        "phone": lead.phone,
        "affiliate_id": broker.affiliate_id,
        "offer_id": broker.offer_id,
    }


def push_lead(broker, lead):
    """Invia il lead a IREV. Ritorna la risposta JSON o solleva IrevError."""
    return _request(broker, "POST", "/api/affiliates/v2/leads",
                    build_push_payload(broker, lead))


def extract_broker_lead_id(response):
    """lead_uuid = id del lead nel sistema IREV (lo salviamo come broker_lead_id;
    il postback ci rimanda lo stesso valore in lead_id)."""
    if isinstance(response, dict):
        return str(response.get("lead_uuid") or response.get("uuid") or "")[:128]
    return ""


def extract_login_url(response):
    if isinstance(response, dict):
        return response.get("auto_login_url") or response.get("autoLoginUrl") or ""
    return ""
