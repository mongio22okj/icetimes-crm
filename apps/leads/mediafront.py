"""Client for the Mediafront lead API (api-mediafront.dev-midas.com).

Config from a LeadSource row (base_url, token, offer_id for boxId,
funnel for sub1). Auth via x-api-key header.

Endpoints:
    POST /customer/lead                              — push a lead
    GET  /customer/integrations-lead?from=…&to=…    — pull leads/deposits
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from .client import CRMAPIError


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.token)


def _request(src, method, path, params=None, body=None, timeout=30):
    if not is_configured(src):
        raise CRMAPIError("Mediafront non configurato: servono URL e API key.")
    url = src.base_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json",
        "x-api-key": src.token,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise CRMAPIError(f"Mediafront HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"Mediafront non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("Mediafront: timeout della richiesta.") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"Mediafront JSON non valido: {raw[:200]}") from exc


def push_lead(src, lead, ip="", user_agent=""):
    body = {
        "email": lead.email,
        "phone": lead.phone,
        "name": lead.firstname,
        "lastName": lead.lastname,
        "country": (lead.country or "IT").upper(),
        "lang": (lead.country or "IT").upper(),
        "ip": ip,
        "userAgent": user_agent or "Mozilla/5.0",
        "boxId": int(src.offer_id) if src.offer_id else None,
        "sub1": src.funnel or "funnel",
    }
    # Rimuovi campi None
    body = {k: v for k, v in body.items() if v is not None}
    result = _request(src, "POST", "/customer/lead", body=body)
    if isinstance(result, dict) and result.get("error"):
        raise CRMAPIError(f"Mediafront: {result.get('message', 'errore sconosciuto')}")
    return result


def list_leads(src, date_from, date_to, is_deposit=None):
    params = {
        "from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    if is_deposit is not None:
        params["isDeposit"] = str(is_deposit).lower()
    return _request(src, "GET", "/customer/integrations-lead", params=params)
