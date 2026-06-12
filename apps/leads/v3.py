"""Client for "Integration v3" broker APIs.

Push-only format used by several broker CRMs:

    POST {base_url}/api/v3/integration?api_token={token}
    Content-Type: application/x-www-form-urlencoded
    Fields: fname, lname, email, fullphone, ip, country, language,
            link_id, funnel, source

link_id / funnel / source come from the LeadSource row.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from .client import CRMAPIError


def is_configured(src) -> bool:
    return bool(src and src.base_url and src.token)


def push_lead(src, payload, timeout=30):
    if not is_configured(src):
        raise CRMAPIError(
            "Integration v3 non configurata: servono URL e api_token nella sorgente."
        )
    url = (src.base_url.rstrip("/") + "/api/v3/integration?api_token="
           + urllib.parse.quote(src.token))
    form = {
        **payload,
        "link_id": src.link_id,
        "funnel": src.funnel,
        "source": src.source_tag,
    }
    req = urllib.request.Request(
        url,
        data=urllib.parse.urlencode(form).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise CRMAPIError(f"Integration v3 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CRMAPIError(f"Integration v3 non raggiungibile: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CRMAPIError("Integration v3: timeout della richiesta.") from exc
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError:
        # Some v3 brokers answer with plain text; keep it raw.
        return {"raw": body[:500]}
