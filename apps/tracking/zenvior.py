"""Client API Zenvior (zenviorcrm.com, deployment "Adverterra").

Auth: `api_key` come query param (niente header), stessa chiave per
push/pull/reporting.

PUSH (registrazione lead): POST {base}/intake?api_key=... (JSON body)
  campi: email O phone (uno dei due obbligatorio), first_name, last_name,
  country (ISO2), offer (nome funnel), click_id (NOSTRO, per aggancio),
  sub1-sub3, language, ip (OBBLIGATORIO: IP reale del visitatore),
  user_agent, is_test.
  Successo: HTTP 200 {"ok": true, "lead_id": 42, "click_id": "abc123"}.
  Errori: 400 (email/phone mancante o dati non validi), 401 (chiave
  invalida), 500 (errore server, ritentare).

PULL (reporting): GET {base}/api/affiliate/leads?api_key=...&page=&limit=
  &status=&from=YYYY-MM-DD&to=YYYY-MM-DD
  Risposta: {"leads":[{id,email,status,sale_status,payout,ftd_date,
  has_conversion,click_id,offer,country,created_at}], page,pages,total}.
  FTD = has_conversion:true (confermato anche da /api/affiliate/conversions,
  che restituisce solo i lead con FTD confermata).
  status: approved | rejected | pending | hold | chargeback.

POSTBACK (broker -> noi): usa il ricevitore GENERICO gia' esistente
  (apps/tracking/postback.py, su /leads/postback/) configurando sul
  pannello Zenvior l'URL:
  https://icetimes.it/leads/postback/?token=<LEADS_POSTBACK_TOKEN>
    &click_id={click_id}&status={status}
  (`click_id` e `status` sono gia' tra le chiavi riconosciute dal
  ricevitore generico). Il postback non manda un flag di deposito
  esplicito -> l'FTD resta affidata alla pull (has_conversion).
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_PUSH_PATH = "/intake"
_PULL_PATH = "/api/affiliate/leads"


class ZenviorError(Exception):
    """Errore di comunicazione con Zenvior."""


def _call(method, url, json_body=None):
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        code = exc.code
        raw = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise ZenviorError(f"non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ZenviorError("timeout della richiesta") from exc
    try:
        obj = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ZenviorError(f"JSON non valido (HTTP {code}): {raw[:150]}") from exc
    if not isinstance(obj, dict):
        obj = {"_raw": obj}
    obj["_http"] = code
    return obj


def build_push_payload(broker, lead):
    return {
        "email": lead.email or "",
        "phone": lead.phone or "",
        "first_name": lead.firstname or "",
        "last_name": lead.lastname or "",
        "country": (lead.country or "IT").upper(),
        "offer": broker.funnel or broker.name,
        "click_id": lead.click_id,
        "ip": lead.ip or "",
    }


def push_lead(broker, lead):
    url = broker.base_url.rstrip("/") + _PUSH_PATH + "?" + urllib.parse.urlencode(
        {"api_key": broker.api_key})
    return _call("POST", url, json_body=build_push_payload(broker, lead))


def extract_broker_lead_id(resp):
    if not isinstance(resp, dict):
        return ""
    v = resp.get("lead_id")
    return str(v) if v not in (None, "") else ""


def pull_leads(broker, date_start=None, date_end=None, page=1, limit=200):
    """GET /api/affiliate/leads. Ritorna (righe della pagina, pagine totali)."""
    params = {"api_key": broker.api_key, "page": page, "limit": limit}
    if date_start:
        params["from"] = date_start
    if date_end:
        params["to"] = date_end
    url = broker.base_url.rstrip("/") + _PULL_PATH + "?" + urllib.parse.urlencode(params)
    resp = _call("GET", url)
    rows = resp.get("leads")
    rows = rows if isinstance(rows, list) else []
    pages = resp.get("pages")
    try:
        pages = int(pages)
    except (TypeError, ValueError):
        pages = 1
    return rows, max(pages, 1)


def is_deposit(row):
    """FTD Zenvior: has_conversion true (confermato anche dall'endpoint
    /api/affiliate/conversions, che elenca solo i lead con FTD)."""
    return bool(row.get("has_conversion"))
