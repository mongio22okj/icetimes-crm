"""Pull/refresh leads from every active source into the local Lead table.

Each source kind has its own routine; `run_all_sources()` dispatches by
kind and returns a list of human-readable result lines (one per source).
"""
from django.utils.dateparse import parse_datetime

from . import affinitrax, client, irev
from .client import CRMAPIError
from .models import Lead, LeadSource
from .sources import active_sources

MAX_PAGES = 30  # safety cap per source: 30 × 100 = 3000 rows


def _paginate(fetch):
    page = 1
    while page <= MAX_PAGES:
        response = fetch(page=page) or {}
        rows = response.get("data") or []
        yield from rows
        pagination = ((response.get("meta") or {}).get("pagination") or {})
        if page >= int(pagination.get("total_pages") or 1):
            break
        page += 1


# ── IREV ─────────────────────────────────────────────────────────────────
def sync_irev_leads(src):
    goals_by_lead = {}
    for conv in _paginate(lambda page: irev.list_conversions(src, page=page)):
        lead_id = conv.get("lead_id")
        if lead_id is not None:
            goals_by_lead.setdefault(str(lead_id), set()).add(
                str(conv.get("goal_type_id") or conv.get("goal_type_uuid") or "")
            )
    ftd_goal = str(src.goal_ftd or "")
    created = updated = 0
    for row in _paginate(lambda page: irev.list_leads(src, page=page)):
        irev_id = row.get("id")
        if irev_id is None:
            continue
        uniqueid = f"irev-{irev_id}"
        goals = goals_by_lead.get(str(irev_id), set())
        is_deposit = bool(ftd_goal and ftd_goal in goals)
        event_at = parse_datetime(row["created_at"]) if isinstance(
            row.get("created_at"), str) else None
        lead = Lead.objects.filter(uniqueid=uniqueid).first()
        if lead is None:
            lead = Lead(uniqueid=uniqueid, source=src.slug)
            created += 1
        else:
            updated += 1
        for field, keys in (
            ("firstname", ("first_name", "firstname")),
            ("lastname", ("last_name", "lastname")),
            ("email", ("email",)),
            ("phone", ("phone",)),
        ):
            for key in keys:
                if row.get(key):
                    setattr(lead, field, str(row[key])[:120])
                    break
        if row.get("country_code"):
            lead.country = str(row["country_code"])[:8]
        if row.get("sale_status"):
            lead.status = str(row["sale_status"])[:120]
        if is_deposit:
            lead.is_deposit = True
        if event_at:
            lead.event_at = event_at
            if lead.pk is None:
                lead.created_at = event_at
        merged = dict(lead.payload or {})
        merged.update(row)
        lead.payload = merged
        lead.save()
    return f"{created} nuovi, {updated} aggiornati"


# ── TrackBox ─────────────────────────────────────────────────────────────
def sync_trackbox_leads(src):
    from datetime import datetime, time, timedelta, timezone as dt_tz

    today = datetime.now(dt_tz.utc).date()
    dt_from = datetime.combine(today - timedelta(days=90), time.min, tzinfo=dt_tz.utc)
    dt_to = datetime.combine(today, time.max, tzinfo=dt_tz.utc)
    response = client.pull_customers(src, dt_from, dt_to)
    created = updated = 0
    for row in client.extract_rows(response):
        if not isinstance(row, dict):
            continue
        uid = str(row.get("uuid") or row.get("id") or "")
        if not uid:
            continue
        uniqueid = f"tb-{uid}"
        lead = Lead.objects.filter(uniqueid=uniqueid).first()
        if lead is None:
            lead = Lead(uniqueid=uniqueid, source=src.slug)
            created += 1
        else:
            updated += 1
        if row.get("callStatus"):
            lead.status = str(row["callStatus"])[:120]
        if row.get("isDeposit"):
            lead.is_deposit = True
        event_at = parse_datetime(str(row.get("createdAt", "")).replace(" ", "T"))
        if event_at:
            lead.event_at = event_at
            if lead.pk is None:
                lead.created_at = event_at
        merged = dict(lead.payload or {})
        merged.update(row)
        lead.payload = merged
        lead.save()
    return f"{created} nuovi, {updated} aggiornati"


# ── Affinitrax ───────────────────────────────────────────────────────────
def refresh_affinitrax_statuses(src, limit=100):
    leads = (Lead.objects
             .filter(source=src.slug, uniqueid__startswith="afx-")
             .filter(status__in=affinitrax.NON_FINAL_STATUSES)
             .order_by("-created_at")[:limit])
    updated = 0
    for lead in leads:
        afx_id = lead.uniqueid.removeprefix("afx-")
        try:
            result = affinitrax.get_lead(src, afx_id) or {}
        except Exception:
            continue
        status = result.get("status") if isinstance(result, dict) else None
        if status and status != lead.status:
            lead.status = str(status)[:120]
            if status == "ftd":
                lead.is_deposit = True
            merged = dict(lead.payload or {})
            merged.update(result)
            lead.payload = merged
            lead.save()
            updated += 1
    return f"{updated} stati aggiornati"


# IREV è escluso dal pull: la sua API di lettura è ristretta per IP (403) e
# non serve, perché IREV ci manda lead e FTD in tempo reale via POSTBACK.
# La funzione sync_irev_leads resta disponibile ma non viene più richiamata.
_DISPATCH = {
    LeadSource.KIND_TRACKBOX: sync_trackbox_leads,
    LeadSource.KIND_AFFINITRAX: refresh_affinitrax_statuses,
}


def run_all_sources():
    """Run sync for every active, pull-capable source. Returns (ok, errors)."""
    ok, errors = [], []
    for src in active_sources():
        if not src.can_pull:
            continue
        fn = _DISPATCH.get(src.kind)
        if not fn:
            continue
        try:
            summary = fn(src)
            ok.append(f"{src.name}: {summary}")
        except CRMAPIError as exc:
            errors.append(f"{src.name}: {exc}")
        except Exception as exc:  # never let one source break the others
            errors.append(f"{src.name}: errore imprevisto ({exc})")
    return ok, errors
