"""Client for the Affinitrax Seller API (e.g. affinitrax.com).

Config from a LeadSource-like `src` (base_url, token). Auth: X-API-Key
header. Endpoints:

    POST /api/v1/leads        — submit a lead (email, phone, country required)
    GET  /api/v1/leads/<id>   — lead status (in_progress|relayed|ftd|rejected)
"""
import json
import urllib.error
import urllib.request

from .client import CRMAPIError

NON_FINAL_STATUSES = ("in_progress", "relayed", "sent")


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.token)


def _request(src, method, path, payload=None, timeout=30):
    if not is_configured(src):
        raise CRMAPIError("Affinitrax non configurato: servono URL e token nella sorgente.")
    url = src.base_url.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": src.token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        try:
            detail = json.loads(detail).get("error", detail)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise CRMAPIError(f"Affinitrax HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"Affinitrax non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("Affinitrax: timeout della richiesta.") from exc
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"Affinitrax JSON non valido: {body[:200]}") from exc


def push_lead(src, payload):
    return _request(src, "POST", "/api/v1/leads", payload=payload)


def get_lead(src, lead_id):
    return _request(src, "GET", f"/api/v1/leads/{lead_id}")
