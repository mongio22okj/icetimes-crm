"""Client API TYourAds (tyourads-api.com).

Push: POST {base_url}/api/v2/leads — auth header 'Api-Key', body form-urlencoded.
Risposta JSON: successo -> details.redirect.url (auto-login); errori in
errors[].message oppure message. Nessun endpoint pull noto: gli stati
arrivano solo via postback se il broker lo supporta.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

_PATH = "/api/v2/leads"
_FIXED_PASSWORD = "qwe123QWE"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


class TYourAdsError(Exception):
    """Errore di comunicazione o risposta non valida da TYourAds."""


def push_lead(broker, lead, timeout=30):
    fields = {
        "firstName": lead.firstname or "",
        "lastName": lead.lastname or "",
        "email": lead.email or "",
        "password": _FIXED_PASSWORD,
        "phone": lead.phone or "",
        "ip": str(lead.ip or ""),
        "custom1": lead.click_id,
        "offerName": broker.offer_name or broker.name,
        "offerWebsite": broker.offer_website or "",
    }
    url = broker.base_url.rstrip("/") + _PATH
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Api-Key": broker.api_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": _UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise TYourAdsError(str(exc))
    try:
        return json.loads(body)
    except Exception:  # noqa: BLE001
        raise TYourAdsError("risposta non-JSON: " + body[:180])


def extract_login_url(resp):
    if isinstance(resp, dict):
        d = resp.get("details") or {}
        r = d.get("redirect") or {}
        return r.get("url") or ""
    return ""


def extract_broker_lead_id(resp):
    if isinstance(resp, dict):
        d = resp.get("details") or {}
        return str(d.get("leadId") or d.get("lead_id") or resp.get("leadId") or "")[:128]
    return ""
