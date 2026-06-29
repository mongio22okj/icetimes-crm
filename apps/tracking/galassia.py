"""Client API 'Galassia' (CRM /api/v3, es. elnopy.crypto-galassia.com).

Push: POST {base_url}/api/v3/integration?api_token=... (form-urlencoded).
  Risposta: {success, id, autologin, password} | {success:false, message}.
Pull: GET {base_url}/api/v3/get-leads?api_token=...&link_id=... (ultimi 7gg).
  Risposta: {success, data:[{id, link_id, acq, registration_date, status}]}.
Aggancio: per 'id' (= broker_lead_id dal push). 'click_id' va nel push per i
postback. FTD = acq == 1.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class GalassiaError(Exception):
    """Errore di comunicazione o risposta non valida da Galassia."""


def _phone(lead):
    p = (lead.phone or "").strip()
    if p and not p.startswith("+"):
        p = "+" + p.lstrip("+")
    return p


def push_lead(broker, lead, timeout=30):
    url = (broker.base_url.rstrip("/") + "/api/v3/integration?api_token="
           + urllib.parse.quote(broker.api_token))
    fields = {
        "link_id": broker.link_id,
        "fname": lead.firstname or "",
        "lname": lead.lastname or "",
        "email": lead.email or "",
        "fullphone": _phone(lead),
        "ip": str(lead.ip or ""),
        "country": (lead.country or broker.country or "IT"),
        "language": broker.language or "it",
        "source": broker.source or "",
        "funnel": broker.funnel or broker.name,
        "click_id": lead.click_id,
    }
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise GalassiaError(str(exc))
    try:
        return json.loads(body)
    except Exception:  # noqa: BLE001
        raise GalassiaError("risposta non-JSON: " + body[:180])


def pull_leads(broker, limit=500, timeout=30):
    url = (broker.base_url.rstrip("/") + "/api/v3/get-leads?api_token="
           + urllib.parse.quote(broker.api_token)
           + "&limit=" + str(limit) + "&link_id=" + urllib.parse.quote(str(broker.link_id)))
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise GalassiaError(str(exc))
    try:
        obj = json.loads(body)
    except Exception:  # noqa: BLE001
        raise GalassiaError("pull non-JSON: " + body[:180])
    return obj.get("data") or [] if isinstance(obj, dict) else []


def extract_login_url(resp):
    return (resp.get("autologin") or "") if isinstance(resp, dict) else ""


def extract_broker_lead_id(resp):
    return str(resp.get("id") or "")[:128] if isinstance(resp, dict) else ""
