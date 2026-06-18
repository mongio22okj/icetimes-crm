"""Client per Hypernet affiliate SDK (HTN-AFF-SDK).

Config da una LeadSource-like `src`:
    base_url        → dominio del tracker (es. https://tracker.broker.com)
    token           → x-api-key (header, stessa chiave per push e pull)
    affiliate_id    → affc (AFF-…)
    hub_id          → bxc  (BX-…)
    vertical_id     → vtc  (VT-…)
    funnel          → nome funnel

Endpoint unico:
    POST /api/external/integration/lead   — crea/push lead
    GET  /api/external/integration/lead   — search lead/stati (skip/take/from/to)

Auth: header ``x-api-key``. Il POST risponde sempre 201 con
``{"success": bool, "redirectUrl": …, "leadId": …, "error"?: …}`` — il
chiamante deve guardare ``success`` (non lo status HTTP) per capire se è
andato a buon fine.
"""
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request

from .client import CRMAPIError

_PATH = "/api/external/integration/lead"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.token
               and src.affiliate_id and src.hub_id and src.vertical_id)


def _headers(src):
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": src.token,
        "User-Agent": _UA,
    }


def _do(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise CRMAPIError(f"Hypernet HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"Hypernet non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("Hypernet: timeout della richiesta.") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"Hypernet JSON non valido: {raw[:200]}") from exc


def push_lead(src, profile, ip, geo="IT", lang="it", landing_lang="it",
              funnel=None, landing_url=None, sub_id="", user_agent=None,
              comment=None, utm=None, timeout=30):
    """POST un lead. `profile` = {firstName,lastName,email,phone,password?}.
    Ritorna il dict di risposta ({success, redirectUrl, leadId, error?})."""
    if not is_configured(src):
        raise CRMAPIError(
            "Hypernet non configurato: servono base_url, x-api-key (token), "
            "affc (affiliate_id), bxc (hub_id) e vtc (vertical_id).")
    phone = re.sub(r"\D", "", str(profile.get("phone") or ""))  # senza +
    body = {
        "affc": src.affiliate_id,
        "bxc": src.hub_id,
        "vtc": src.vertical_id,
        "profile": {
            "firstName": (profile.get("firstName") or profile.get("first_name") or "")[:120],
            "lastName": (profile.get("lastName") or profile.get("last_name") or "")[:120],
            "email": (profile.get("email") or "")[:254],
            "password": profile.get("password") or secrets.token_urlsafe(10),
            "phone": phone,
        },
        "ip": ip or "",
        "funnel": (funnel or src.funnel or src.name or "icetimes")[:120],
        "landingURL": landing_url or (
            f"https://icetimes.it/b/{src.landing_slug}/" if src.landing_slug
            else src.base_url),
        "geo": (geo or "IT").upper(),
        "lang": (lang or "it").lower(),
        "landingLang": (landing_lang or "it").lower(),
    }
    if user_agent:
        body["userAgent"] = user_agent
    if comment:
        body["comment"] = comment
    if sub_id:
        body["subId"] = str(sub_id)[:255]
    for k in ("utmSource", "utmMedium", "utmCampaign", "utmId"):
        if utm and utm.get(k):
            body[k] = utm[k]
    url = src.base_url.rstrip("/") + _PATH
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="POST", headers=_headers(src))
    return _do(req, timeout)


def pull_leads(src, skip=0, take=250, dt_from=None, dt_to=None, timeout=30):
    """GET lead/stati. Ritorna la lista `rows` (ogni row: id, registration,
    profile, isDeposited, depositedAt, …). `dt_from`/`dt_to` sono ISO-8601."""
    if not (src and src.base_url and src.token):
        raise CRMAPIError("Hypernet non configurato: servono base_url e x-api-key.")
    query = {"skip": skip, "take": take}
    if dt_from:
        query["from"] = dt_from
    if dt_to:
        query["to"] = dt_to
    url = src.base_url.rstrip("/") + _PATH + "?" + urllib.parse.urlencode(query)
    headers = {"Accept": "application/json", "x-api-key": src.token, "User-Agent": _UA}
    req = urllib.request.Request(url, method="GET", headers=headers)
    data = _do(req, timeout)
    if isinstance(data, dict):
        return data.get("rows") or []
    return data if isinstance(data, list) else []
