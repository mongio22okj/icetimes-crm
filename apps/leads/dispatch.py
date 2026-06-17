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
from django.utils import timezone

from . import affinitrax, client, irev, mediafront, spmmonster, v3
from .client import CRMAPIError
from .models import DispatchLog, Lead, LeadSource


def _extract_broker_lead_id(response):
    """Normalizza l'id-lead ritornato dai vari broker dopo un push accettato.

    Serve a riagganciare i postback di stato/FTD al lead esatto: il broker
    rimanda questo id, noi lo salviamo in payload['broker_lead_id'] così il
    postback fa match preciso invece di ripiegare sull'email (ambigua).
    """
    if not isinstance(response, dict):
        return None
    for key in ("lead_uuid", "lead_id", "leadId", "id", "customerId", "uuid"):
        val = response.get(key)
        if val:
            return str(val)[:128]
    # Alcuni broker annidano: {"data": {"id": …}}.
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("id", "lead_id", "uuid"):
            if data.get(key):
                return str(data[key])[:128]
    return None


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
        p = lead.payload or {}
        payload = {
            "firstname": lead.firstname,
            "lastname": lead.lastname,
            "email": lead.email,
            "phone": lead.phone,
            "password": secrets.token_urlsafe(10),
            # TrackBox richiede un userip valido: usa l'IP reale del
            # visitatore (catturato dalla landing in payload['ip']), con
            # fallback per non far fallire il push se manca.
            "userip": p.get("ip") or "8.8.8.8",
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
    """Push `lead` to its broker. Returns list of attempt dicts.

    `sources`: explicit list of broker(s) to push to. If None, il lead va
    SOLO al suo broker di provenienza (lead.source) — i lead non vengono
    MAI smistati a cascata su più broker.
    `stop_on_success`: si ferma al primo broker che accetta (rilevante solo
    se viene passata una lista esplicita di più broker).
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
        # I lead NON vengono MAI smistati tra broker: ogni lead va SOLO al
        # suo broker di provenienza (lead.source = slug del broker, es.
        # "trackbox-14"). Se non si risale a un broker push-capable preciso,
        # non si fa alcun dispatch — niente cascata sugli altri broker.
        own = next(
            (s for s in LeadSource.objects.filter(is_active=True)
             if s.slug == (lead.source or "") and s.can_push),
            None,
        )
        sources = [own] if own else []

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

        broker_lead_id = _extract_broker_lead_id(response) if success else None
        if success:
            # Persisti l'attribuzione per agganciare i postback futuri al
            # lead esatto. Mappa per-broker (non sovrascrive gli altri) +
            # 'broker_lead_id' top-level = ultimo accettante (winner del
            # ping-tree), che è quello che riceverà i postback di stato/FTD.
            payload = dict(lead.payload or {})
            attributions = dict(payload.get("broker_attributions") or {})
            attributions[source.slug] = {
                "broker_lead_id": broker_lead_id,
                "at": timezone.now().isoformat(),
            }
            payload["broker_attributions"] = attributions
            if broker_lead_id:
                payload["broker_lead_id"] = broker_lead_id
                # uniqueid resta vuoto se il lead arriva da postback senza id;
                # lo settiamo solo se mancante per non rompere match esistenti.
                if not lead.uniqueid:
                    lead.uniqueid = broker_lead_id
                    Lead.objects.filter(pk=lead.pk).update(
                        payload=payload, uniqueid=broker_lead_id)
                else:
                    Lead.objects.filter(pk=lead.pk).update(payload=payload)
            else:
                Lead.objects.filter(pk=lead.pk).update(payload=payload)
            lead.payload = payload

        attempts.append({
            "source": source,
            "success": success,
            "latency_ms": latency_ms,
            "error": error_msg,
            "broker_lead_id": broker_lead_id,
        })
        if success and stop_on_success:
            break

    return attempts
