"""Sync stati lead via PULL API broker (TrackBox).

Update-only: aggancia le righe della pull ai NOSTRI lead e aggiorna
status/FTD. Niente import di lead esterni (non creiamo lead che non
abbiamo mandato noi).
"""
from datetime import datetime, timedelta, timezone as dt_tz

from django.utils.dateparse import parse_datetime

from . import spmmonster, trackbox
from .models import Lead

MAX_PAGES = 30

# Chiavi candidate (in ordine) per gli id e gli stati nelle righe della pull,
# il cui schema non è rigidamente documentato.
_ID_KEYS = ("affclickid", "click_id", "clickid", "aff_click_id",
            "uniqueid", "customer_id", "customerId", "id", "lead_id")
_STATUS_KEYS = ("call_status", "callStatus", "status", "saleStatus",
                "sale_status", "statusName")
_DEPOSIT_KEYS = ("depositor", "isDeposit", "isDeposited", "deposit", "ftd")


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


def _match_lead(broker, row):
    """Trova un nostro lead dalla riga della pull: per click_id (affclickid)
    o broker_lead_id. Solo lead del broker giusto (segregazione)."""
    ids = _candidate_ids(row)
    if not ids:
        return None
    qs = Lead.for_broker(broker)
    return (qs.filter(click_id__in=ids).first()
            or qs.filter(broker_lead_id__in=ids).first())


def sync_broker(broker, days=90):
    """Pull degli stati per un broker e aggiornamento dei nostri lead.

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
            matched += 1
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
        page += 1
    return {"seen": seen, "matched": matched, "updated": updated, "pages": page}


# ── SPM Monster (Hypernet) ───────────────────────────────────────────────
def sync_spmmonster(broker, days=90):
    """Pull stati SPM Monster (GET /api/external/integration/lead). Aggancio
    per subId (=click_id) o id (=broker_lead_id). Stato da registration.status,
    FTD da isDeposited. Solo lead del broker."""
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
        if lead is None:
            continue
        matched += 1
        reg = row.get("registration") if isinstance(row.get("registration"), dict) else {}
        status = reg.get("status") or reg.get("rawStatus")
        changed = False
        if status and lead.status != str(status)[:120]:
            lead.status = str(status)[:120]
            changed = True
        is_dep = bool(row.get("isDeposited")) or str(status or "").strip().lower() == "deposited"
        if is_dep and not lead.is_deposit:
            lead.is_deposit = True
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
    return {"seen": seen, "matched": matched, "updated": updated, "pages": 1}
