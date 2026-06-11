"""Thin client for the TrackBox lead API (track.fintechgurus.org).

Uses urllib from the standard library so no new dependency enters the
locked dependency tree. Endpoints (Tigloo TrackBox docs):

    POST /api/pull/customers      — read leads/deposits in a date range
    POST /api/signup/procform     — push a new lead

Every call requires the headers x-trackbox-username, x-trackbox-password
and x-api-key. Configuration comes from environment variables:
TRACKBOX_BASE_URL, TRACKBOX_USERNAME, TRACKBOX_PASSWORD, TRACKBOX_API_KEY,
TRACKBOX_AI, TRACKBOX_CI, TRACKBOX_GI.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings

# TrackBox pull "type" values.
PULL_LEADS = "2"
PULL_LEADS_AND_DEPOSITS = "3"
PULL_DEPOSITS = "4"

# Date format TrackBox expects in pull from/to params.
API_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class CRMAPIError(Exception):
    """Raised when the TrackBox API is unconfigured, unreachable, or errors."""


def is_configured() -> bool:
    return all([
        settings.TRACKBOX_BASE_URL,
        settings.TRACKBOX_USERNAME,
        settings.TRACKBOX_PASSWORD,
        settings.TRACKBOX_API_KEY,
    ])


def _request(path, payload, timeout=25):
    if not is_configured():
        raise CRMAPIError(
            "TrackBox non configurato: servono TRACKBOX_BASE_URL, "
            "TRACKBOX_USERNAME, TRACKBOX_PASSWORD e TRACKBOX_API_KEY "
            "nelle variabili d'ambiente."
        )
    url = settings.TRACKBOX_BASE_URL.rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-trackbox-username": settings.TRACKBOX_USERNAME,
            "x-trackbox-password": settings.TRACKBOX_PASSWORD,
            "x-api-key": settings.TRACKBOX_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise CRMAPIError(f"TrackBox ha risposto HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"TrackBox non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("TrackBox: timeout della richiesta.") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"TrackBox ha restituito JSON non valido: {body[:200]}") from exc

    # TrackBox wraps errors in {"status": false, "message": ..., "code": ...}.
    if isinstance(data, dict) and data.get("status") is False:
        raise CRMAPIError(
            f"TrackBox: {data.get('message', 'errore sconosciuto')} "
            f"(code {data.get('code', '?')})"
        )
    return data


def pull_customers(date_from, date_to, pull_type=PULL_LEADS_AND_DEPOSITS, page=0):
    """Return leads/deposits between two datetimes (TrackBox pull API)."""
    payload = {
        "from": date_from.strftime(API_DATE_FORMAT),
        "to": date_to.strftime(API_DATE_FORMAT),
        "type": str(pull_type),
        "page": str(page),
    }
    return _request("/api/pull/customers", payload)


def push_lead(payload):
    """Submit a new lead (TrackBox signup API). ai/ci/gi come from settings."""
    body = {
        "ai": settings.TRACKBOX_AI,
        "ci": settings.TRACKBOX_CI,
        "gi": settings.TRACKBOX_GI,
        **payload,
    }
    return _request("/api/signup/procform", body)


def extract_rows(response):
    """Normalize the pull response into a list of dicts.

    The exact response shape isn't documented; tolerate the common
    wrappings: a bare list, {"data": [...]}, or {"data": {"customers"|
    "leads": [...]}}.
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        data = response.get("data", response)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("customers", "leads", "rows", "items"):
                if isinstance(data.get(key), list):
                    return data[key]
    return []
