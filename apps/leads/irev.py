"""Client for the IREV affiliate API (e.g. stylishwnt.com).

Config from a LeadSource-like `src` (base_url, token, offer_id,
goal_ftd). Auth is a ``token`` query param; the token is IP-whitelisted
on the IREV side. Endpoints:

    GET  /api/v1/affiliates/leads          — pull leads (paginated)
    GET  /api/v1/affiliates/conversions    — pull conversions
    POST /api/v1/affiliates/leads          — push a lead (form-encoded)
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from .client import CRMAPIError


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.token)


def _request(src, method, path, params=None, form=None, timeout=30):
    if not is_configured(src):
        raise CRMAPIError("IREV non configurato: servono URL e token nella sorgente.")
    query = {"token": src.token, **(params or {})}
    url = src.base_url.rstrip("/") + path + "?" + urllib.parse.urlencode(query)
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
                "IREV ha rifiutato la connessione (403): l'IP del server non è "
                "nella whitelist del token. Far autorizzare gli IP outbound di "
                "Render dal partner IREV."
            ) from exc
        raise CRMAPIError(f"IREV HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"IREV non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("IREV: timeout della richiesta.") from exc
    try:
        return json.loads(body) if body else None
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"IREV JSON non valido: {body[:200]}") from exc


def list_leads(src, created_from=None, created_to=None, page=1, per_page=100):
    params = {"page": page, "per_page": per_page}
    if created_from:
        params["created_from"] = created_from
    if created_to:
        params["created_to"] = created_to
    return _request(src, "GET", "/api/v1/affiliates/leads", params=params)


def list_conversions(src, created_from=None, created_to=None, page=1, per_page=100):
    params = {"page": page, "per_page": per_page}
    if created_from:
        params["created_from"] = created_from
    if created_to:
        params["created_to"] = created_to
    return _request(src, "GET", "/api/v1/affiliates/conversions", params=params)


def push_lead(src, profile, ip, tp_source="icetimes-crm", subs=None, aff_sub5=None):
    form = {"ip": ip, "tp_source": tp_source}
    if src.offer_id:
        form["tp_offer_id"] = src.offer_id
    for key, value in (profile or {}).items():
        form[f"profile[{key}]"] = value
    for i, value in enumerate(subs or [], start=1):
        suffix = "" if i == 1 else str(i)
        form[f"tp_aff_sub{suffix}"] = value
    # IREV vuole il nostro click id in aff_sub5 (lo rimanda nel postback).
    if aff_sub5:
        form["tp_aff_sub5"] = aff_sub5
    return _request(src, "POST", "/api/v1/affiliates/leads", form=form)
