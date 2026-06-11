"""Thin client for the external CRM lead API (x-api-key auth).

Uses urllib from the standard library so no new dependency enters the
locked dependency tree. Endpoints (see Postman docs):

    GET  /customer/integrations-lead?from=&to=&isDeposit=
    POST /customer/lead

Both require the ``x-api-key`` header. Base URL and key come from the
``CRM_API_BASE_URL`` / ``CRM_API_KEY`` environment variables.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

# ISO-8601 UTC format the API expects for the from/to range params.
API_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"


class CRMAPIError(Exception):
    """Raised when the CRM API is unconfigured, unreachable, or errors."""


def is_configured() -> bool:
    return bool(settings.CRM_API_BASE_URL and settings.CRM_API_KEY)


def _request(method, path, *, params=None, payload=None, timeout=20):
    if not is_configured():
        raise CRMAPIError(
            "CRM API non configurata: impostare le variabili d'ambiente "
            "CRM_API_BASE_URL e CRM_API_KEY."
        )
    url = settings.CRM_API_BASE_URL.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "x-api-key": settings.CRM_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise CRMAPIError(f"CRM API ha risposto HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"CRM API non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("CRM API: timeout della richiesta.") from exc
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"CRM API ha restituito JSON non valido: {body[:200]}") from exc


def get_leads(date_from, date_to, is_deposit=None):
    """Return the lead list for the datetime range [date_from, date_to]."""
    params = {
        "from": date_from.strftime(API_DATE_FORMAT),
        "to": date_to.strftime(API_DATE_FORMAT),
    }
    if is_deposit is not None:
        params["isDeposit"] = "true" if is_deposit else "false"
    result = _request("GET", "/customer/integrations-lead", params=params)
    return result if isinstance(result, list) else []


def send_lead(payload):
    """Submit a new lead; returns the API response (status/uuid/autologinLink)."""
    return _request("POST", "/customer/lead", payload=payload)
