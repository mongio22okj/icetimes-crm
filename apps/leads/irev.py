"""Client for the IREV affiliate API (stylishwnt.com).

Auth is a ``token`` request parameter (NOT a header); the token is bound
to whitelisted static IPs on the IREV side — calls from non-whitelisted
IPs get a bare nginx 403. Endpoints (Aff API IREV doc):

    GET  /api/v1/affiliates/leads          — pull leads (paginated)
    GET  /api/v1/affiliates/conversions    — pull conversions (lead/FTD)
    GET  /api/v1/affiliates/goal-types     — goal catalogue
    GET  /api/v1/affiliates/fields         — lead profile field keys
    POST /api/v1/affiliates/leads          — push a lead (form-encoded)

Configuration via env: IREV_BASE_URL, IREV_TOKEN, IREV_AFFILIATE_ID,
IREV_OFFER_ID, IREV_GOAL_LEAD, IREV_GOAL_FTD.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

from .client import CRMAPIError


def is_configured() -> bool:
    return bool(settings.IREV_BASE_URL and settings.IREV_TOKEN)


def _request(method, path, params=None, form=None, timeout=30):
    if not is_configured():
        raise CRMAPIError(
            "IREV non configurato: impostare IREV_BASE_URL e IREV_TOKEN "
            "nelle variabili d'ambiente."
        )
    query = {"token": settings.IREV_TOKEN, **(params or {})}
    url = (settings.IREV_BASE_URL.rstrip("/") + path
           + "?" + urllib.parse.urlencode(query))
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    headers = {"Accept": "application/json"}
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        if exc.code == 403:
            raise CRMAPIError(
                "IREV ha rifiutato la connessione (403): l'IP del server "
                "non è nella whitelist del token. Far autorizzare gli IP "
                "outbound di Render dal partner IREV."
            ) from exc
        raise CRMAPIError(f"IREV ha risposto HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"IREV non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("IREV: timeout della richiesta.") from exc
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"IREV ha restituito JSON non valido: {body[:200]}") from exc


def list_leads(created_from=None, created_to=None, page=1, per_page=100):
    params = {"page": page, "per_page": per_page}
    if created_from:
        params["created_from"] = created_from
    if created_to:
        params["created_to"] = created_to
    return _request("GET", "/api/v1/affiliates/leads", params=params)


def list_conversions(created_from=None, created_to=None, page=1, per_page=100):
    params = {"page": page, "per_page": per_page}
    if created_from:
        params["created_from"] = created_from
    if created_to:
        params["created_to"] = created_to
    return _request("GET", "/api/v1/affiliates/conversions", params=params)


def goal_types():
    return _request("GET", "/api/v1/affiliates/goal-types")


def profile_fields():
    return _request("GET", "/api/v1/affiliates/fields")


def push_lead(profile, ip, tp_source="icetimes-crm", subs=None):
    """POST a lead. `profile` maps field keys (email, phone, first_name…)."""
    form = {"ip": ip, "tp_source": tp_source}
    if settings.IREV_OFFER_ID:
        form["tp_offer_id"] = settings.IREV_OFFER_ID
    for key, value in (profile or {}).items():
        form[f"profile[{key}]"] = value
    for i, value in enumerate(subs or [], start=1):
        suffix = "" if i == 1 else str(i)
        form[f"tp_aff_sub{suffix}"] = value
    return _request("POST", "/api/v1/affiliates/leads", form=form)
