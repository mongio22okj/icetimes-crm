"""Sync stati lead via PULL API broker (TrackBox).

Update-only: aggancia le righe della pull ai NOSTRI lead e aggiorna
status/FTD. Niente import di lead esterni (non creiamo lead che non
abbiamo mandato noi).
"""
from datetime import datetime, timedelta, timezone as dt_tz

from django.utils.dateparse import parse_datetime

from . import spmmonster, trackbox
from .models import Lead, status_to_stage

MAX_PAGES = 30

# Chiavi candidate (in ordine) per gli id e gli stati nelle righe della pull,
# il cui schema non è rigidamente documentato.
_ID_KEYS = ("affclickid", "click_id", "clickid", "aff_click_id",
            "uniqueid", "customer_id", "customerId", "id", "lead_id")
_STATUS_KEYS = ("call_status", "callStatus", "status", "saleStatus",
                "sale_status", "statusName")
_DEPOSIT_KEYS = ("depositor", "isDeposit", "isDeposited", "deposit", "ftd")
_EMAIL_KEYS = ("email", "customerEmail", "mail", "emailAddress", "e_mail")
_PHONE_KEYS = ("phone", "phoneNumber", "telephone", "mobile",
               "customerPhone", "tel")


def _first(row, *keys):
    for key in keys:
        val = row.get(key)
        if val not in (None, "", "null"):
            return val
    return None


def _truthy(value) -> bool:
    return str(value).strip().lower() in {
        "1", "true", "yes", "y", "deposit", "ftd", "depositor"}


def _candidate_ids(row):
    out = []
    for key in _ID_KEYS:
        val = row.get(key)
        if val not in (None, "", "null"):
            out.append(str(val))
    return out


def _deep_first(row, keys):
    """Cerca le chiavi a top-level e nei dict annidati piu' comuni: ogni broker
    annida i dati diversamente (profile, customerData, registration...)."""
    if not isinstance(row, dict):
        return None
    v = _first(row, *keys)
    if v is not None:
        return v
    for nest in ("profile", "customerData", "customer", "customerInfo",
                 "data", "lead", "registration"):
        sub = row.get(nest)
        if isinstance(sub, dict):
            v = _first(sub, *keys)
            if v is not None:
                return v
    return None


def match_lead_by_contact(qs, row, allow_ambiguous=False):
    """Rete di sicurezza universale (i broker espongono campi diversi):
    aggancia per email, poi telefono (ultime 9 cifre). `qs` va gia' filtrato sul
    broker quando possibile. Con allow_ambiguous=False aggancia SOLO se unica
    (percorsi non segregati come il postback)."""
    email = _deep_first(row, _EMAIL_KEYS)
    if email:
        ms = list(qs.filter(email__iexact=str(email).strip())[:2])
        if ms and (allow_ambiguous or len(ms) == 1):
            return ms[0]
    phone = _deep_first(row, _PHONE_KEYS)
    if phone:
        digits = "".join(ch for ch in str(phone) if ch.isdigit())
        if len(digits) >= 9:
            ms = list(qs.filter(phone__endswith=digits[-9:])[:2])
            if ms and (allow_ambiguous or len(ms) == 1):
                return ms[0]
    return None


def _match_lead(broker, row):
    """Aggancia una riga della pull al nostro lead: prima per click_id
    (affclickid) o broker_lead_id, poi per email/telefono. Sempre e solo tra i
    lead del broker giusto (segregazione)."""
    qs = Lead.for_broker(broker)
    ids = _candidate_ids(row)
    if ids:
        m = (qs.filter(click_id__in=ids).first()
             or qs.filter(broker_lead_id__in=ids).first())
        if m:
            return m
    # Fallback email/telefono SOLO per i broker che lo richiedono (es. Link 10).
    if getattr(broker, "match_by_contact", False):
        return match_lead_by_contact(qs, row, allow_ambiguous=True)
    return None


def sync_broker(broker, days=90, only_ids=None):
    """Pull degli stati per un broker e aggiornamento dei nostri lead.

    only_ids: se valorizzato (set di pk), aggiorna SOLO quei lead.
    Ritorna un dict: {seen, matched, updated, pages}.
    """
    now = datetime.now(dt_tz.utc)
    dt_from = now - timedelta(days=days)
    seen = matched = updated = 0
    page = 0
    while page < MAX_PAGES:
        response = trackbox.pull_customers(broker, dt_from, now, page=page)
        rows = trackbox.extract_rows(response)
        if not rows:
            break
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            seen += 1
            row = raw.get("customerData") if isinstance(raw.get("customerData"), dict) else raw
            lead = _match_lead(broker, row)
            if lead is None:
                continue
            if only_ids is not None and lead.pk not in only_ids:
                continue
            matched += 1
            lead.last_pull_at = now
            changed = False
            status = _first(row, *_STATUS_KEYS)
            if status and lead.status != str(status)[:120]:
                lead.status = str(status)[:120]
                changed = True
            is_dep = (_truthy(_first(row, *_DEPOSIT_KEYS))
                      or str(status or "").strip().lower() in {"ftd", "deposit", "depositor"})
            if is_dep and not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            new_stage = "ftd" if is_dep else status_to_stage(status)
            if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                lead.stage = new_stage
                changed = True
            ev = _first(row, "depositDate", "depositedAt", "createdAt", "date")
            if isinstance(ev, str) and not lead.event_at:
                lead.event_at = parse_datetime(ev.replace(" ", "T"))
                changed = True
            if changed:
                merged = dict(lead.payload or {})
                merged["last_pull"] = row
                lead.payload = merged
                lead.save()
                updated += 1
            else:
                lead.save(update_fields=["last_pull_at"])
        page += 1
    return {"seen": seen, "matched": matched, "updated": updated, "pages": page}


# ── SPM Monster (Hypernet) ───────────────────────────────────────────────
def sync_spmmonster(broker, days=90, only_ids=None):
    """Pull stati SPM Monster (GET /api/external/integration/lead). Aggancio
    per subId (=click_id) o id (=broker_lead_id). Stato da registration.status,
    FTD da isDeposited. Solo lead del broker. only_ids: solo quei lead."""
    now = datetime.now(dt_tz.utc)
    rows = spmmonster.pull_leads(broker, now - timedelta(days=days), now)
    seen = matched = updated = 0
    qs = Lead.for_broker(broker)
    for row in rows:
        if not isinstance(row, dict):
            continue
        seen += 1
        rid = str(row.get("id") or "")
        sub = str(row.get("subId") or "")
        lead = None
        if sub:
            lead = qs.filter(click_id=sub).first()
        if lead is None and rid:
            lead = qs.filter(broker_lead_id=rid).first() or qs.filter(click_id=rid).first()
        if lead is None and getattr(broker, "match_by_contact", False):
            lead = match_lead_by_contact(qs, row, allow_ambiguous=True)
        if lead is None:
            continue
        if only_ids is not None and lead.pk not in only_ids:
            continue
        matched += 1
        lead.last_pull_at = now
        reg = row.get("registration") if isinstance(row.get("registration"), dict) else {}
        # rawStatus = esito reale chiamata (CALLBACK, NO_ANSWER, Not interest...);
        # status = solo "sent"/"deposited". Preferisci il dettaglio.
        status = reg.get("rawStatus") or reg.get("status")
        changed = False
        if status and lead.status != str(status)[:120]:
            lead.status = str(status)[:120]
            changed = True
        is_dep = (bool(row.get("isDeposited"))
                  or str(reg.get("status") or "").strip().lower() == "deposited"
                  or str(status or "").strip().lower() in {"deposited", "ftd", "deposit"})
        if is_dep and not lead.is_deposit:
            lead.is_deposit = True
            changed = True
        new_stage = "ftd" if is_dep else status_to_stage(status)
        if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
            lead.stage = new_stage
            changed = True
        dep = row.get("depositedAt")
        if isinstance(dep, str) and dep and not lead.event_at:
            lead.event_at = parse_datetime(dep.replace(" ", "T"))
            changed = True
        if rid and not lead.broker_lead_id:
            lead.broker_lead_id = rid
            changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged["last_pull"] = row
            lead.payload = merged
            lead.save()
            updated += 1
        else:
            lead.save(update_fields=["last_pull_at"])
    return {"seen": seen, "matched": matched, "updated": updated, "pages": 1}


# ── Sync di TUTTI i broker pull-capable (TrackBox + SPM) ─────────────────
def sync_all_pullable():
    """Lancia la pull/sync per ogni broker attivo TrackBox + SPM Monster.
    IREV è escluso (stato via postback). Ritorna un riepilogo aggregato."""
    from .models import TrackboxBroker, SpmMonsterBroker
    total = {"updated": 0, "matched": 0, "seen": 0, "brokers": 0, "errors": []}
    jobs = ([(b, sync_broker) for b in TrackboxBroker.objects.filter(is_active=True)]
            + [(b, sync_spmmonster) for b in SpmMonsterBroker.objects.filter(is_active=True)])
    for broker, fn in jobs:
        try:
            r = fn(broker)
            total["updated"] += r["updated"]
            total["matched"] += r["matched"]
            total["seen"] += r["seen"]
            total["brokers"] += 1
        except Exception as exc:  # noqa: BLE001
            total["errors"].append(f"{broker.name}: {exc}")
    return total


def sync_selected(lead_ids):
    """Pull/sync degli stati SOLO per i lead selezionati. Raggruppa per broker,
    fa una pull per broker e aggiorna unicamente i lead spuntati. IREV escluso
    (stato via postback). Ritorna riepilogo aggregato."""
    from .models import SpmMonsterBroker, TrackboxBroker
    ids = {int(x) for x in lead_ids}
    total = {"updated": 0, "matched": 0, "seen": 0, "brokers": 0,
             "errors": [], "irev": 0}
    brokers = {}
    for lead in Lead.objects.filter(pk__in=ids):
        b = lead.broker
        if b is not None:
            brokers[(type(b).__name__, b.pk)] = b
    for b in brokers.values():
        try:
            if isinstance(b, TrackboxBroker):
                r = sync_broker(b, only_ids=ids)
            elif isinstance(b, SpmMonsterBroker):
                r = sync_spmmonster(b, only_ids=ids)
            else:
                total["irev"] += 1  # IREV: stato via postback, no pull
                continue
            total["updated"] += r["updated"]
            total["matched"] += r["matched"]
            total["seen"] += r["seen"]
            total["brokers"] += 1
        except Exception as exc:  # noqa: BLE001
            total["errors"].append(f"{b.name}: {exc}")
    return total
