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
                "IREV pull rifiutato (403): l'API di lettura "
                "/api/v1/affiliates/ è ristretta per IP lato IREV e l'IP del "
                "nostro server (80.211.136.232) non è autorizzato. NB: il push "
                "dei lead funziona comunque — i lead arrivano in tempo reale "
                "via postback. Per abilitare la sync manuale, chiedere a IREV "
                "di mettere in whitelist l'IP 80.211.136.232 sull'API affiliati."
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
    """Push a lead via l'endpoint v2 (quello reale usato dalla funnel).

    POST {base_url}/affiliates/v2/leads, body JSON, token nell'header
    ``Authorization``. Mappatura ricavata dal send.php funzionante:
    aff_sub2=affiliate_id, aff_sub4=funnel/offerta, aff_sub5=click id.
    Risposta 200: {lead_uuid, auto_login_url}.
    """
    import secrets

    body = {
        "first_name": profile.get("first_name") or profile.get("firstname") or "",
        "last_name": profile.get("last_name") or profile.get("lastname") or "",
        "email": profile.get("email") or "",
        "phone": profile.get("phone") or "",
        "password": secrets.token_urlsafe(8),
        "ip": ip or "",
        "aff_sub2": src.affiliate_id or "",
        "aff_sub5": aff_sub5 or "",
    }
    if src.funnel:
        body["aff_sub4"] = src.funnel
    if str(src.offer_id).isdigit():
        body["offer_id"] = int(src.offer_id)
    elif src.offer_id:
        body["offer_id"] = src.offer_id
    if str(src.affiliate_id).isdigit():
        body["affiliate_id"] = int(src.affiliate_id)
    elif src.affiliate_id:
        body["affiliate_id"] = src.affiliate_id

    url = src.base_url.rstrip("/") + "/affiliates/v2/leads"
    return _post_json(src, url, body)


def _post_json(src, url, body, timeout=30):
    if not is_configured(src):
        raise CRMAPIError("IREV non configurato: servono URL e token nella sorgente.")
    data = json.dumps(body).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": src.token,  # token grezzo, senza "Bearer"
        # Cloudflare di stylishwnt.com blocca lo UA "Python-urllib" (403):
        # serve uno UA da browser per passare il WAF.
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
    }
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise CRMAPIError(f"IREV HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"IREV non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("IREV: timeout della richiesta.") from exc
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"IREV JSON non valido: {raw[:200]}") from exc


def pull_leads_v2(src, page=1, per_page=100, created_from=None, created_to=None, timeout=30):
    """Pull leads/stati via la **v2** (GET /affiliates/v2/leads). Ritorna una
    LISTA di lead (uuid, leadUuid, saleStatus, goalTypeUuid, email, …).
    NB: la v1 (/api/v1/affiliates/) è ristretta per IP lato IREV; la v2 no,
    e usa lo stesso token del push nell'header Authorization.
    `per_page` ha **max 100** lato IREV (valori più alti vengono tagliati);
    senza `created_from` l'API torna i lead più VECCHI per primi → per i
    recenti bisogna paginare e/o passare una finestra `created_from`."""
    from urllib.parse import urlencode
    if not is_configured(src):
        raise CRMAPIError("IREV non configurato: servono URL e token nella sorgente.")
    query = {"per_page": per_page, "page": page}
    if created_from:
        query["created_from"] = created_from
    if created_to:
        query["created_to"] = created_to
    url = src.base_url.rstrip("/") + "/affiliates/v2/leads?" + urlencode(query)
    headers = {
        "Accept": "application/json",
        "Authorization": src.token,  # token grezzo, come il push v2
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
    }
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise CRMAPIError(f"IREV HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"IREV non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("IREV: timeout della richiesta.") from exc
    try:
        data = json.loads(raw) if raw else []
    except json.JSONDecodeError as exc:
        raise CRMAPIError(f"IREV JSON non valido: {raw[:200]}") from exc
    return data if isinstance(data, list) else (data.get("data") or [])
