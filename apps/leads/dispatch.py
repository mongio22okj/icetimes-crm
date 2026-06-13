"""Ping-tree multi-broker dispatch.

Given a Lead, iterates active push-capable LeadSource objects in priority
order (lowest .priority first). Pushes the lead to each broker via the
existing client modules (trackbox, irev, affinitrax, v3) until one
accepts. Every attempt — success or failure — is logged to DispatchLog.

This implements the "ping-tree" pattern: multiple buyers ranked by
priority, lead is offered down the list until accepted.
"""
import secrets
import time

from . import affinitrax, client, irev, mediafront, spmmonster, v3
from .client import CRMAPIError
from .models import DispatchLog, LeadSource


def _push(lead, source):
    """Call the kind-specific push_lead and return (ok, response)."""
    if source.kind == LeadSource.KIND_TRACKBOX:
        payload = {
            "firstname": lead.firstname,
            "lastname": lead.lastname,
            "email": lead.email,
            "phone": lead.phone,
            "password": secrets.token_urlsafe(10),
            "userip": "",
            "country": (lead.country or "IT").upper(),
            "lg": (lead.country or "IT").upper(),
            "affclickid": f"ice{secrets.token_hex(6)}",
        }
        return True, client.push_lead(source, payload) or {}

    if source.kind == LeadSource.KIND_IREV:
        profile = {
            "email": lead.email,
            "phone": lead.phone,
            "first_name": lead.firstname,
            "last_name": lead.lastname,
        }
        result = irev.push_lead(source, profile, ip="") or {}
        if isinstance(result, dict) and result.get("validation_errors"):
            return False, result
        return True, result

    if source.kind == LeadSource.KIND_AFFINITRAX:
        click_id = f"ice{secrets.token_hex(6)}"
        payload = {
            "email": lead.email,
            "phone": lead.phone,
            "first_name": lead.firstname,
            "last_name": lead.lastname,
            "country": (lead.country or "IT").upper(),
            "ip": "",
            "click_id": click_id,
        }
        return True, affinitrax.push_lead(source, payload) or {}

    if source.kind == LeadSource.KIND_V3:
        payload = {
            "fname": lead.firstname,
            "lname": lead.lastname,
            "email": lead.email,
            "fullphone": lead.phone,
            "ip": "",
            "country": (lead.country or "IT").upper(),
            "language": (lead.country or "IT").lower(),
        }
        return True, v3.push_lead(source, payload) or {}

    if source.kind == LeadSource.KIND_MEDIAFRONT:
        result = mediafront.push_lead(source, lead) or {}
        return True, result

    if source.kind == LeadSource.KIND_SPMMONSTER:
        result = spmmonster.push_lead(source, lead) or {}
        return True, result

    return False, {"error": f"unsupported kind: {source.kind}"}


def dispatch(lead, sources=None, stop_on_success=True):
    """Run the ping-tree for `lead`. Returns list of attempt dicts.

    `sources`: explicit ordered list; defaults to every active push-
    capable LeadSource ordered by priority.
    `stop_on_success`: True = stop at first accepting broker (classic
    ping-tree). False = always offer to every broker.
    """
    if sources is None:
        sources = list(
            LeadSource.objects.filter(is_active=True)
            .order_by("priority", "name")
        )
        sources = [s for s in sources if s.can_push]

    attempts = []
    for source in sources:
        t0 = time.monotonic()
        success = False
        response = {}
        error_msg = ""
        try:
            ok, response = _push(lead, source)
            success = bool(ok)
            if not success:
                error_msg = str(response.get("error") or response)[:255] if isinstance(response, dict) else str(response)[:255]
        except CRMAPIError as e:
            error_msg = str(e)[:255]
        except Exception as e:  # noqa: BLE001
            error_msg = f"{type(e).__name__}: {e}"[:255]
        latency_ms = int((time.monotonic() - t0) * 1000)

        DispatchLog.objects.create(
            lead=lead,
            source=source,
            source_name=source.name,
            success=success,
            response=response if isinstance(response, dict) else {"raw": str(response)[:1000]},
            latency_ms=latency_ms,
            error=error_msg,
        )
        attempts.append({
            "source": source,
            "success": success,
            "latency_ms": latency_ms,
            "error": error_msg,
        })
        if success and stop_on_success:
            break

    return attempts
