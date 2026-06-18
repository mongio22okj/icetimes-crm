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


# ── IREV (pull v2: GET /affiliates/v2/leads) ─────────────────────────────
def sync_irev_leads(src):
    """Aggiorna gli stati dei NOSTRI lead IREV via la pull **v2**.
    Update-only: aggancia per `leadUuid` (= il nostro `uniqueid`) e aggiorna
    `saleStatus` + FTD (`goalTypeUuid == goal_ftd`). NON importa lead esterni
    (segregazione per broker). La v1 era ristretta per IP → la v2 no."""
    ftd_goal = str(src.goal_ftd or "")
    updated = 0
    page = 1
    while page <= MAX_PAGES:
        rows = irev.pull_leads_v2(src, page=page, per_page=500)
        if not rows:
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            lead_uuid = str(row.get("leadUuid") or row.get("uuid") or "")
            if not lead_uuid:
                continue
            lead = Lead.objects.filter(uniqueid=lead_uuid).first()
            if lead is None:
                continue  # solo i nostri lead, niente import esterni
            changed = False
            status = row.get("saleStatus")
            if status and lead.status != str(status)[:120]:
                lead.status = str(status)[:120]
                changed = True
            goal = str(row.get("goalTypeUuid") or "")
            is_dep = (bool(ftd_goal) and goal == ftd_goal) or \
                str(status or "").strip().lower() in {"ftd", "deposit", "depositor"}
            if is_dep and not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            ev = row.get("createdAt")
            if isinstance(ev, str) and not lead.event_at:
                lead.event_at = parse_datetime(ev.replace(" ", "T"))
                changed = True
            if changed:
                merged = dict(lead.payload or {})
                merged.update(row)
                lead.payload = merged
                lead.save()
                updated += 1
        if len(rows) < 500:
            break
        page += 1
    return f"{updated} stati aggiornati (pull v2)"


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


# Gli STATUS si leggono via PULL API (non dal postback). IREV ora usa la **v2**
# (`/affiliates/v2/leads`) che NON è ristretta per IP (la v1 lo era), quindi è
# attiva. TrackBox resta escluso finché non gestiamo la sua chiave di PULL
# (diversa da quella di push).
_DISPATCH = {
    LeadSource.KIND_AFFINITRAX: refresh_affinitrax_statuses,
    LeadSource.KIND_IREV: sync_irev_leads,
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
