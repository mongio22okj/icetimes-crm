"""Client for the Affinitrax Seller API (affinitrax.com).

Auth: X-API-Key header (afx_… token). Endpoints (docs/seller-api):

    POST /api/v1/leads        — submit a lead (email, phone, country required)
    GET  /api/v1/leads/<id>   — lead status (in_progress|relayed|ftd|rejected)

Status updates also arrive via postback (configured on the Affinitrax
side towards /leads/postback/ with {click_id}/{event_type} placeholders).
Configuration via env: AFFINITRAX_BASE_URL, AFFINITRAX_API_KEY.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .client import CRMAPIError

# Lead statuses that are still expected to change on the Affinitrax side.
NON_FINAL_STATUSES = ("in_progress", "relayed", "sent")


def is_configured() -> bool:
    return bool(settings.AFFINITRAX_BASE_URL and settings.AFFINITRAX_API_KEY)


def _request(method, path, payload=None, timeout=30):
    if not is_configured():
        raise CRMAPIError(
            "Affinitrax non configurato: impostare AFFINITRAX_BASE_URL e "
            "AFFINITRAX_API_KEY nelle variabili d'ambiente."
        )
    url = settings.AFFINITRAX_BASE_URL.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-Key": settings.AFFINITRAX_API_KEY,
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


def push_lead(payload):
    """POST a lead; returns {lead_id, status, redirect_url}."""
    return _request("POST", "/api/v1/leads", payload=payload)


def get_lead(lead_id):
    """Return current status payload for a lead id."""
    return _request("GET", f"/api/v1/leads/{lead_id}")
