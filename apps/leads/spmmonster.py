"""Client for the SPM Monster lead API (spm.monster).

Config from a LeadSource row:
  base_url  → https://spm.monster
  token     → x-api-key
  ai        → affc (affiliate code)
  ci        → bxc  (box code)
  gi        → vtc  (vertical/template code)
  funnel    → funnel name

Endpoints:
  POST /api/external/integration/lead   — push a lead
  GET  /api/external/integration/lead?from=…&to=…  — pull leads
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
        raise CRMAPIError("SPM Monster non configurato: servono URL e API key.")
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
        raise CRMAPIError(f"SPM Monster HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"SPM Monster non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("SPM Monster: timeout della richiesta.") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"SPM Monster JSON non valido: {raw[:200]}") from exc


def push_lead(src, lead, ip="", landing_url=""):
    import secrets
    body = {
        "affc": src.ai,
        "bxc": src.ci,
        "vtc": src.gi,
        "profile": {
            "firstName": lead.firstname,
            "lastName": lead.lastname,
            "email": lead.email,
            "password": secrets.token_urlsafe(10),
            "phone": lead.phone,
        },
        "ip": ip or "",
        "geo": (lead.country or "IT").upper(),
        "lang": (lead.country or "IT").upper(),
        "landingLang": (lead.country or "IT").upper(),
        "funnel": src.funnel or "icetimes",
        "landingURL": landing_url or src.base_url,
        "subId": f"ice{secrets.token_hex(4)}",
    }
    result = _request(src, "POST", "/api/external/integration/lead", body=body)
    if isinstance(result, dict) and not result.get("success"):
        raise CRMAPIError(f"SPM Monster: {result.get('error', 'errore sconosciuto')}")
    return result


def list_leads(src, date_from, date_to):
    params = {
        "from": date_from.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "to": date_to.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }
    return _request(src, "GET", "/api/external/integration/lead", params=params)
