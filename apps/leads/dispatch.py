"""Ping-tree multi-broker dispatch.

Given a Lead, iterates active push-capable LeadSource objects in priority
order (lowest .priority first). Pushes the lead to each broker via the
existing client modules (trackbox, irev, affinitrax, v3) until one
accepts. Every attempt — success or failure — is logged to DispatchLog.

This implements the "ping-tree" pattern: multiple buyers ranked by
priority, lead is offered down the list until accepted.
"""
import re
import secrets
import time

from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from . import affinitrax, client, irev, mediafront, spmmonster, v3
from .client import CRMAPIError
from .models import DispatchLog, LeadSource


def validate_and_normalize(lead):
    """Pulisce e valida un lead prima del push verso i broker.

    Normalizza email (lower/strip) e telefono (mantiene un eventuale +
    iniziale, rimuove tutto ciò che non è cifra) e li ri-salva sul lead
    se cambiati. Ritorna (ok, reason). I broker rifiutano i lead con
    email/telefono/nome mancanti o invalidi con HTTP 422, quindi è inutile
    tentare il dispatch: meglio bloccarli qui.
    """
    changed = []

    email = (lead.email or "").strip().lower()
    if email != (lead.email or ""):
        lead.email = email
        changed.append("email")

    raw_phone = (lead.phone or "").strip()
    plus = raw_phone.startswith("+")
    digits = re.sub(r"\D", "", raw_phone)
    norm_phone = ("+" if plus else "") + digits
    if norm_phone != (lead.phone or ""):
        lead.phone = norm_phone
        changed.append("phone")

    first = (lead.firstname or "").strip()
    if first != (lead.firstname or ""):
        lead.firstname = first
        changed.append("firstname")

    if changed:
        lead.save(update_fields=changed)

    problems = []
    if not email:
        problems.append("email mancante")
    else:
        try:
            validate_email(email)
        except ValidationError:
            problems.append("email non valida")
    if len(digits) < 7:
        problems.append("telefono mancante/non valido")
    if not first:
        problems.append("nome mancante")

    if problems:
        return False, "; ".join(problems)
    return True, ""


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
        payload = lead.payload or {}
        click = (payload.get("aff_sub5") or payload.get("click_id")
                 or payload.get("cid") or "")
        ip = payload.get("ip") or "8.8.8.8"  # IREV richiede un ip valido
        result = irev.push_lead(source, profile, ip=ip, aff_sub5=click) or {}
        if isinstance(result, dict) and result.get("validation_errors"):
            return False, result
        return True, result

    if source.kind == LeadSource.KIND_AFFINITRAX:
        p = lead.payload or {}
        click_id = (p.get("aff_sub5") or p.get("click_id") or p.get("cid")
                    or f"ice{secrets.token_hex(6)}")
        payload = {
            "email": lead.email,
            "phone": lead.phone,
            "first_name": lead.firstname,
            "last_name": lead.lastname,
            "country": (lead.country or "IT").upper(),
            "ip": p.get("ip") or "",
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
        p = lead.payload or {}
        result = mediafront.push_lead(
            source, lead,
            ip=p.get("ip") or "",
            user_agent=p.get("user_agent") or p.get("userAgent") or "",
        ) or {}
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
    ok, reason = validate_and_normalize(lead)
    if not ok:
        DispatchLog.objects.create(
            lead=lead,
            source=None,
            source_name="(validazione)",
            success=False,
            response={"blocked": reason},
            latency_ms=0,
            error=f"Lead bloccato pre-push: {reason}"[:255],
        )
        return [{"source": None, "success": False, "latency_ms": 0,
                 "error": f"Lead bloccato pre-push: {reason}"}]

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
