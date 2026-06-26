"""Pull/refresh leads from every active source into the local Lead table.

Each source kind has its own routine; `run_all_sources()` dispatches by
kind and returns a list of human-readable result lines (one per source).
"""
import logging

from django.utils.dateparse import parse_datetime

from . import affinitrax, client, hypernet, irev, mediafront, spmmonster
from .client import CRMAPIError
from .models import Lead, LeadSource
from .sources import active_sources

logger = logging.getLogger(__name__)

MAX_PAGES = 30  # safety cap per source: 30 × 100 = 3000 rows

# Chiavi candidate (provate in ordine) per leggere i campi dai pull "generici"
# di broker il cui schema di risposta non è rigidamente documentato.
_ID_KEYS = ("id", "leadId", "lead_id", "uuid", "customerId", "leadUuid",
            "uniqueid")
_STATUS_KEYS = ("status", "saleStatus", "call_status", "callStatus",
                "leadStatus", "statusName", "registrationStatus")
_DEPOSIT_KEYS = ("isDeposit", "isDeposited", "deposit", "ftd", "depositor",
                 "hasFtd")


def _first(row, *keys):
    """Primo valore non vuoto tra `keys` in `row` (dict)."""
    for key in keys:
        val = row.get(key)
        if val not in (None, "", "null"):
            return val
    return None


def _rows_from(response):
    """Normalizza un payload di pull in una lista di righe.

    I broker rispondono in modi diversi: lista nuda, {"data": [...]},
    {"leads": [...]} o {"result": [...]}. Ritorna sempre una lista.
    """
    if isinstance(response, list):
        return response
    if isinstance(response, dict):
        for key in ("data", "leads", "result", "items", "rows"):
            val = response.get(key)
            if isinstance(val, list):
                return val
    return []


def _match_lead(row):
    """Aggancia una riga di pull a un NOSTRO lead per id broker.

    Prova prima `uniqueid` (su tutte le chiavi id candidate), poi il
    `broker_lead_id` salvato nel payload al push. Niente match per email
    (ambiguo / cross-broker). Ritorna il Lead o None — nessun import di
    lead esterni (segregazione per broker).
    """
    rid = _first(row, *_ID_KEYS)
    if not rid:
        return None
    rid = str(rid)
    lead = Lead.objects.filter(uniqueid=rid).order_by("-created_at").first()
    if lead is None:
        lead = (Lead.objects.filter(payload__broker_lead_id=rid)
                .order_by("-created_at").first())
    return lead


def _apply_generic_update(lead, row):
    """Applica status/FTD/event_at da una riga generica. Ritorna True se cambiato."""
    changed = False
    status = _first(row, *_STATUS_KEYS)
    if status and lead.status != str(status)[:120]:
        lead.status = str(status)[:120]
        changed = True
    dep_raw = _first(row, *_DEPOSIT_KEYS)
    is_dep = str(dep_raw).strip().lower() in {"1", "true", "yes", "deposit",
                                              "ftd", "depositor"} \
        or str(status or "").strip().lower() in {"ftd", "deposit", "depositor"}
    if is_dep and not lead.is_deposit:
        lead.is_deposit = True
        changed = True
    ev = _first(row, "createdAt", "depositedAt", "date", "time", "eventDate")
    if isinstance(ev, str) and not lead.event_at:
        lead.event_at = parse_datetime(ev.replace(" ", "T"))
        changed = True
    if changed:
        merged = dict(lead.payload or {})
        merged.update(row)
        lead.payload = merged
        lead.save()
    return changed


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
    from datetime import datetime, timedelta, timezone as dt_tz
    ftd_goal = str(src.goal_ftd or "")
    # API IREV: per_page max 100; senza created_from torna i lead più VECCHI
    # per primi → senza bound non vedremmo i recenti. Finestra 90gg + paginazione.
    PER_PAGE = 100
    created_from = (datetime.now(dt_tz.utc) - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = 0
    page = 1
    while page <= MAX_PAGES:
        rows = irev.pull_leads_v2(src, page=page, per_page=PER_PAGE, created_from=created_from)
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
        if len(rows) < PER_PAGE:
            break
        page += 1
    return f"{updated} stati aggiornati (pull v2)"


# ── TrackBox (pull: POST /api/pull/customers) ────────────────────────────
def sync_trackbox_leads(src):
    """Aggiorna gli stati dei NOSTRI lead TrackBox via la pull. La chiave di
    pull (DIVERSA dal push) sta in `src.pull_token`. Update-only: aggancia per
    `customerData.uniqueid` (= il nostro `uniqueid`), status da `call_status`,
    FTD da `depositor`. Non importa lead esterni (segregazione)."""
    if not src.pull_token:
        return "pull key (pull_token) mancante — skip"
    from datetime import datetime, time, timedelta, timezone as dt_tz
    today = datetime.now(dt_tz.utc).date()
    dt_from = datetime.combine(today - timedelta(days=90), time.min, tzinfo=dt_tz.utc)
    dt_to = datetime.combine(today, time.max, tzinfo=dt_tz.utc)
    response = client.pull_customers(src, dt_from, dt_to)
    updated = 0
    for row in client.extract_rows(response):
        if not isinstance(row, dict):
            continue
        cd = row.get("customerData") if isinstance(row.get("customerData"), dict) else row
        uid = str(cd.get("uniqueid") or cd.get("customer_id") or "")
        if not uid:
            continue
        lead = Lead.objects.filter(uniqueid=uid).first()
        if lead is None:
            continue  # solo i nostri lead, niente import esterni
        changed = False
        status = cd.get("call_status")
        if status and lead.status != str(status)[:120]:
            lead.status = str(status)[:120]
            changed = True
        if str(cd.get("depositor")) in ("1", "True", "true") and not lead.is_deposit:
            lead.is_deposit = True
            changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged.update(cd)
            lead.payload = merged
            lead.save()
            updated += 1
    return f"{updated} stati aggiornati (pull)"


# ── Hypernet (pull: GET /api/external/integration/lead) ──────────────────
def sync_hypernet_leads(src):
    """Aggiorna gli stati dei NOSTRI lead Hypernet via la pull. Update-only:
    aggancia per `id` (= il nostro `uniqueid`, ovvero il leadId del push),
    status da `registration.status`, FTD da `isDeposited`/`depositedAt`. Non
    importa lead esterni (segregazione per broker)."""
    from datetime import datetime, timedelta, timezone as dt_tz
    now = datetime.now(dt_tz.utc)
    dt_from = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    dt_to = now.strftime("%Y-%m-%dT%H:%M:%S.999Z")
    TAKE = 250
    updated = 0
    skip = 0
    while skip < TAKE * MAX_PAGES:
        rows = hypernet.pull_leads(src, skip=skip, take=TAKE,
                                   dt_from=dt_from, dt_to=dt_to)
        if not rows:
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            rid = str(row.get("id") or "")
            if not rid:
                continue
            lead = Lead.objects.filter(uniqueid=rid).first()
            if lead is None:
                continue  # solo i nostri lead, niente import esterni
            changed = False
            reg = row.get("registration") if isinstance(row.get("registration"), dict) else {}
            status = reg.get("status") or reg.get("rawStatus")
            if status and lead.status != str(status)[:120]:
                lead.status = str(status)[:120]
                changed = True
            if row.get("isDeposited") and not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            dep = row.get("depositedAt")
            if isinstance(dep, str) and not lead.event_at:
                lead.event_at = parse_datetime(dep.replace(" ", "T"))
                changed = True
            if changed:
                merged = dict(lead.payload or {})
                merged.update(row)
                lead.payload = merged
                lead.save()
                updated += 1
        if len(rows) < TAKE:
            break
        skip += TAKE
    return f"{updated} stati aggiornati (pull)"


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


# ── Mediafront (pull: GET /customer/integrations-lead) ───────────────────
def sync_mediafront_leads(src):
    """Aggiorna gli stati dei NOSTRI lead Mediafront via la pull. Update-only:
    aggancia per id broker (= nostro `uniqueid`/`broker_lead_id`), status/FTD
    dai campi della riga. Non importa lead esterni (segregazione)."""
    from datetime import datetime, timedelta, timezone as dt_tz
    now = datetime.now(dt_tz.utc)
    dt_from = now - timedelta(days=90)
    response = mediafront.list_leads(src, dt_from, now)
    updated = 0
    for row in _rows_from(response):
        if not isinstance(row, dict):
            continue
        lead = _match_lead(row)
        if lead is None:
            continue  # solo i nostri lead, niente import esterni
        if _apply_generic_update(lead, row):
            updated += 1
    return f"{updated} stati aggiornati (pull)"


# ── SPM Monster (pull: GET /api/external/integration/lead) ───────────────
def sync_spmmonster_leads(src):
    """Aggiorna gli stati dei NOSTRI lead SPM Monster via la pull. Update-only:
    aggancia per id broker, status/FTD dai campi della riga. Non importa lead
    esterni (segregazione per broker)."""
    from datetime import datetime, timedelta, timezone as dt_tz
    now = datetime.now(dt_tz.utc)
    dt_from = now - timedelta(days=90)
    response = spmmonster.list_leads(src, dt_from, now)
    updated = 0
    for row in _rows_from(response):
        if not isinstance(row, dict):
            continue
        lead = _match_lead(row)
        if lead is None:
            continue  # solo i nostri lead, niente import esterni
        if _apply_generic_update(lead, row):
            updated += 1
    return f"{updated} stati aggiornati (pull)"


# Gli STATUS si leggono via PULL API (non dal postback). IREV ora usa la **v2**
# (`/affiliates/v2/leads`) che NON è ristretta per IP (la v1 lo era), quindi è
# attiva. Ogni broker pull-capable (vedi LeadSource.PULL_KINDS) DEVE avere qui
# una funzione: una sorgente in PULL_KINDS ma assente da _DISPATCH non
# aggiornerebbe mai gli stati (lead congelati su "inviato"). run_all_sources
# logga un warning se trova questo buco di configurazione.
_DISPATCH = {
    LeadSource.KIND_AFFINITRAX: refresh_affinitrax_statuses,
    LeadSource.KIND_IREV: sync_irev_leads,
    LeadSource.KIND_TRACKBOX: sync_trackbox_leads,
    LeadSource.KIND_HYPERNET: sync_hypernet_leads,
    LeadSource.KIND_MEDIAFRONT: sync_mediafront_leads,
    LeadSource.KIND_SPMMONSTER: sync_spmmonster_leads,
}


def run_all_sources():
    """Run sync for every active, pull-capable source. Returns (ok, errors)."""
    ok, errors = [], []
    for src in active_sources():
        if not src.can_pull:
            continue
        fn = _DISPATCH.get(src.kind)
        if not fn:
            # Sorgente dichiarata pull-capable ma senza routine di sync: gli
            # stati resterebbero congelati e prima il salto era silenzioso.
            msg = (f"{src.name}: nessuna routine di pull per kind "
                   f"'{src.kind}' — stati NON aggiornati (canale pull mancante)")
            logger.warning(msg)
            errors.append(msg)
            continue
        try:
            summary = fn(src)
            ok.append(f"{src.name}: {summary}")
        except CRMAPIError as exc:
            errors.append(f"{src.name}: {exc}")
        except Exception as exc:  # never let one source break the others
            errors.append(f"{src.name}: errore imprevisto ({exc})")
    return ok, errors
