"""Client for the TrackBox lead API (e.g. track.fintechgurus.org).

Config comes from a LeadSource-like object (`src`) carrying base_url,
username, password, token (x-api-key) and ai/ci/gi. Endpoints:

    POST /api/pull/customers      — read leads/deposits in a date range
    POST /api/signup/procform     — push a new lead
"""
import json
import urllib.error
import urllib.request

# TrackBox pull "type" values.
PULL_LEADS = "2"
PULL_LEADS_AND_DEPOSITS = "3"
PULL_DEPOSITS = "4"

# Date format TrackBox expects in pull from/to params.
API_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class CRMAPIError(Exception):
    """Raised when an external lead API is unconfigured, unreachable, or errors."""


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.username and src.password and src.token)


def _request(src, path, payload, timeout=25):
    if not is_configured(src):
        raise CRMAPIError(
            "TrackBox non configurato: servono URL, username, password e "
            "token (x-api-key) nella sorgente."
        )
    url = src.base_url.rstrip("/") + path
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-trackbox-username": src.username,
            "x-trackbox-password": src.password,
            "x-api-key": src.token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise CRMAPIError(f"TrackBox HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"TrackBox non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("TrackBox: timeout della richiesta.") from exc
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"TrackBox JSON non valido: {body[:200]}") from exc

    if isinstance(data, dict) and data.get("status") is False:
        raise CRMAPIError(
            f"TrackBox: {data.get('message', 'errore sconosciuto')} "
            f"(code {data.get('code', '?')})"
        )
    return data


def pull_customers(src, date_from, date_to, pull_type=PULL_LEADS_AND_DEPOSITS, page=0):
    payload = {
        "from": date_from.strftime(API_DATE_FORMAT),
        "to": date_to.strftime(API_DATE_FORMAT),
        "type": str(pull_type),
        "page": str(page),
    }
    return _request(src, "/api/pull/customers", payload)


def push_lead(src, payload):
    body = {"ai": src.ai, "ci": src.ci or "1", "gi": src.gi, **payload}
    return _request(src, "/api/signup/procform", body)


def extract_rows(response):
    """Normalize a pull response into a list of dicts."""
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
