"""Pull-sync from the IREV affiliate API into the local Lead table.

Upserts on uniqueid "irev-<id>" so re-running is idempotent; deposit
flags come from conversions whose goal matches IREV_GOAL_FTD.
"""
from django.conf import settings
from django.utils.dateparse import parse_datetime

from . import irev
from .models import Lead

MAX_PAGES = 30  # safety cap: 30 × 100 = 3000 rows per run


def _paginate(fetch):
    """Yield rows across pages until the API reports the last page."""
    page = 1
    while page <= MAX_PAGES:
        response = fetch(page=page) or {}
        rows = response.get("data") or []
        yield from rows
        pagination = ((response.get("meta") or {}).get("pagination") or {})
        if page >= int(pagination.get("total_pages") or 1):
            break
        page += 1


def sync_irev_leads():
    """Returns (created, updated). Raises CRMAPIError on API failure."""
    # Conversions first: map lead_id → set of goal ids.
    goals_by_lead = {}
    for conv in _paginate(irev.list_conversions):
        lead_id = conv.get("lead_id")
        if lead_id is not None:
            goals_by_lead.setdefault(str(lead_id), set()).add(
                str(conv.get("goal_type_id") or conv.get("goal_type_uuid") or "")
            )

    ftd_goal = str(settings.IREV_GOAL_FTD or "")
    created = updated = 0
    for row in _paginate(irev.list_leads):
        irev_id = row.get("id")
        if irev_id is None:
            continue
        uniqueid = f"irev-{irev_id}"
        goals = goals_by_lead.get(str(irev_id), set())
        is_deposit = bool(ftd_goal and ftd_goal in goals)
        event_at = None
        if isinstance(row.get("created_at"), str):
            event_at = parse_datetime(row["created_at"])

        lead = Lead.objects.filter(uniqueid=uniqueid).first()
        if lead is None:
            lead = Lead(uniqueid=uniqueid, source="irev")
            created += 1
        else:
            updated += 1
        # The list payload may or may not include profile/contact fields
        # depending on the IREV setup — map what's there, keep the rest raw.
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
                # New row: date it when IREV created it, not when we synced.
                lead.created_at = event_at
        merged = dict(lead.payload or {})
        merged.update(row)
        lead.payload = merged
        lead.save()
    return created, updated
