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
def sync_galassia(broker, days=90, only_ids=None):
    """Pull stati Galassia (GET /api/v3/get-leads). Aggancio per broker_lead_id
    (= id Galassia). Stato da 'status'; FTD da acq==1. Solo lead del broker."""
    from . import galassia
    now = datetime.now(dt_tz.utc)
    rows = galassia.pull_leads(broker)
    seen = matched = updated = 0
    qs = Lead.for_broker(broker)
    for row in rows:
        if not isinstance(row, dict):
            continue
        seen += 1
        rid = str(row.get("id") or "")
        lead = qs.filter(broker_lead_id=rid).first() if rid else None
        if lead is None and getattr(broker, "match_by_contact", False):
            lead = match_lead_by_contact(qs, row, allow_ambiguous=True)
        if lead is None:
            continue
        if only_ids is not None and lead.pk not in only_ids:
            continue
        matched += 1
        lead.last_pull_at = now
        status = row.get("status")
        changed = False
        if status and lead.status != str(status)[:120]:
            lead.status = str(status)[:120]
            changed = True
        is_dep = (str(row.get("acq")) == "1"
                  or str(status or "").strip().lower() in {"ftd", "deposit", "deposited"})
        if is_dep and not lead.is_deposit:
            lead.is_deposit = True
            changed = True
        new_stage = "ftd" if is_dep else status_to_stage(status)
        if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
            lead.stage = new_stage
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


def sync_openaff(broker, days=90, only_ids=None):
    """Pull stati OpenAFF (GET get_client_conversions, Bearer token).
    Aggancio per aff_sub (= nostro click_id), poi click_id/id (= broker_lead_id).
    Stato da lead_status; FTD = conversion_type == 'Conversion'. Solo lead del
    broker. Interroga giorno per giorno la finestra richiesta."""
    from . import openaff
    now = datetime.now(dt_tz.utc)
    qs = Lead.for_broker(broker)
    seen = updated = 0
    matched_pks = set()
    # OpenAFF vuole una data per richiesta: iteriamo i giorni della finestra.
    for d in range(days + 1):
        day = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        try:
            rows = openaff.pull_conversions(broker, date=day, all_statuses=True)
        except openaff.OpenAffError:
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            seen += 1
            sub = str(row.get("aff_sub") or "").strip()
            rid = str(row.get("id") or "").strip()
            cid = str(row.get("click_id") or "").strip()
            lead = None
            if sub:
                lead = qs.filter(click_id=sub).first()
            if lead is None and rid:
                lead = qs.filter(broker_lead_id=rid).first() or qs.filter(click_id=rid).first()
            if lead is None and cid:
                lead = qs.filter(broker_lead_id=cid).first()
            if lead is None and getattr(broker, "match_by_contact", False):
                lead = match_lead_by_contact(qs, row, allow_ambiguous=True)
            if lead is None:
                continue
            if only_ids is not None and lead.pk not in only_ids:
                continue
            matched_pks.add(lead.pk)
            lead.last_pull_at = now
            changed = False
            conv = str(row.get("conversion_type") or "").strip().lower()
            status = row.get("lead_status") or row.get("conversion_type")
            is_dep = (conv == "conversion")
            if is_dep:
                if not lead.is_deposit:
                    lead.is_deposit = True
                    changed = True
                if lead.status != "FTD":
                    lead.status = "FTD"
                    changed = True
                if lead.stage != "ftd":
                    lead.stage = "ftd"
                    changed = True
            else:
                if status and lead.status != str(status)[:120]:
                    lead.status = str(status)[:120]
                    changed = True
                new_stage = status_to_stage(status)
                if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                    lead.stage = new_stage
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
    return {"seen": seen, "matched": len(matched_pks), "updated": updated, "pages": 1}


def sync_globaltrade(broker, days=90, only_ids=None):
    """Pull stati GlobalTrade (GET /api/web-master/leads, Bearer token).
    Righe reali: {id, email, status:{id,name}, is_action, action_time, date}.
    Aggancio per broker_lead_id (= id) o email; status = status.name;
    FTD quando status_to_stage(status) == 'ftd'."""
    from . import globaltrade
    now = datetime.now(dt_tz.utc)
    qs = Lead.for_broker(broker)
    seen = updated = 0
    matched_pks = set()
    date_start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    date_end = now.strftime("%Y-%m-%d")
    try:
        rows = globaltrade.pull_leads(broker, date_start=date_start, date_end=date_end)
    except globaltrade.GlobalTradeError:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        seen += 1
        bid = str(row.get("id") or "").strip()
        email = str(row.get("email") or "").strip()
        st = row.get("status")
        status = (st.get("name") or st.get("id")) if isinstance(st, dict) else st
        lead = None
        if bid:
            lead = qs.filter(broker_lead_id=bid).first()
        if lead is None and email:
            lead = qs.filter(email__iexact=email).first()
        if lead is None:
            continue
        if only_ids is not None and lead.pk not in only_ids:
            continue
        matched_pks.add(lead.pk)
        lead.last_pull_at = now
        changed = False
        is_dep = status_to_stage(status) == "ftd"
        if is_dep:
            if not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            if lead.status != "FTD":
                lead.status = "FTD"
                changed = True
            if lead.stage != "ftd":
                lead.stage = "ftd"
                changed = True
        else:
            if status and lead.status != str(status)[:120]:
                lead.status = str(status)[:120]
                changed = True
            new_stage = status_to_stage(status)
            if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                lead.stage = new_stage
                changed = True
        if bid and not lead.broker_lead_id:
            lead.broker_lead_id = bid
            changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged["last_pull"] = row
            lead.payload = merged
            lead.save()
            updated += 1
        else:
            lead.save(update_fields=["last_pull_at"])
    return {"seen": seen, "matched": len(matched_pks), "updated": updated, "pages": 1}


def sync_onecrypt(broker, days=90, only_ids=None):
    """Pull stati OneCrypt (GET /api/lead/feed). Aggancio per id2 (= nostro
    click_id) o id (= broker_lead_id). L'esito-chiamata reale sta in `comment`;
    lo `status` è il ciclo new/holded/confirmed/cancelled. FTD = confirmed/
    confirmed_compensation."""
    from . import onecrypt
    now = datetime.now(dt_tz.utc)
    qs = Lead.for_broker(broker)
    seen = updated = 0
    matched_pks = set()
    date_start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    date_end = now.strftime("%Y-%m-%d")
    try:
        rows = onecrypt.pull_leads(broker, date_start=date_start, date_end=date_end)
    except onecrypt.OneCryptError:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        seen += 1
        our = str(row.get("id2") or "").strip()   # = nostro click_id
        their = str(row.get("id") or "").strip()   # = broker_lead_id
        lead = None
        if our:
            lead = qs.filter(click_id=our).first()
        if lead is None and their:
            lead = qs.filter(broker_lead_id=their).first()
        if lead is None:
            continue
        if only_ids is not None and lead.pk not in only_ids:
            continue
        matched_pks.add(lead.pk)
        lead.last_pull_at = now
        changed = False
        st = str(row.get("status") or "").strip().lower()
        is_dep = onecrypt.is_deposit(row)
        # esito-chiamata reale in `comment`, fallback su status. Alcuni feed
        # OneCrypt infilano nel comment il dump della risposta
        # ({'id':..,'autologin_url':..}): scartiamo la parte tra graffe per non
        # sporcare lo status; se resta vuoto usiamo il campo status.
        raw_status = str(row.get("comment") or "").strip()
        if "{" in raw_status:
            raw_status = raw_status.split("{", 1)[0].strip().rstrip("\\").strip()
        if not raw_status:
            raw_status = str(row.get("status") or "").strip()
        if is_dep:
            if not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            if lead.status != "FTD":
                lead.status = "FTD"
                changed = True
            if lead.stage != "ftd":
                lead.stage = "ftd"
                changed = True
        else:
            if raw_status and lead.status != str(raw_status)[:120]:
                lead.status = str(raw_status)[:120]
                changed = True
            new_stage = status_to_stage(raw_status)
            if not new_stage and st == "cancelled":
                new_stage = "not_interested"
            if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                lead.stage = new_stage
                changed = True
        if their and not lead.broker_lead_id:
            lead.broker_lead_id = their
            changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged["last_pull"] = row
            lead.payload = merged
            lead.save()
            updated += 1
        else:
            lead.save(update_fields=["last_pull_at"])
    return {"seen": seen, "matched": len(matched_pks), "updated": updated, "pages": 1}


def sync_cpaforge(broker, days=90, only_ids=None):
    """Pull stati CPAForge (GET /api/v2/leads). Aggancio per custom1 (= nostro
    click_id) o leadRequestIDEncoded (= broker_lead_id). Stato-chiamata in
    `saleStatus`; FTD = hasFTD == 1."""
    from . import cpaforge
    now = datetime.now(dt_tz.utc)
    qs = Lead.for_broker(broker)
    seen = updated = 0
    matched_pks = set()
    date_start = (now - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    date_end = now.strftime("%Y-%m-%d %H:%M:%S")
    try:
        rows = cpaforge.pull_leads(broker, date_start=date_start, date_end=date_end)
    except cpaforge.CpaForgeError:
        rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        seen += 1
        our = str(row.get("custom1") or "").strip()          # = nostro click_id
        their = str(row.get("leadRequestIDEncoded") or "").strip()  # = broker_lead_id
        lead = None
        if our:
            lead = qs.filter(click_id=our).first()
        if lead is None and their:
            lead = qs.filter(broker_lead_id=their).first()
        if lead is None and broker.match_by_contact:
            email = (row.get("customerID") or "").strip()
            if email and "@" in email:
                lead = qs.filter(email__iexact=email).first()
        if lead is None:
            continue
        if only_ids is not None and lead.pk not in only_ids:
            continue
        matched_pks.add(lead.pk)
        lead.last_pull_at = now
        changed = False
        is_dep = cpaforge.is_deposit(row)
        raw_status = row.get("saleStatus")
        if is_dep:
            if not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            if lead.status != "FTD":
                lead.status = "FTD"
                changed = True
            if lead.stage != "ftd":
                lead.stage = "ftd"
                changed = True
        else:
            if raw_status and lead.status != str(raw_status)[:120]:
                lead.status = str(raw_status)[:120]
                changed = True
            new_stage = status_to_stage(raw_status)
            if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                lead.stage = new_stage
                changed = True
        if their and not lead.broker_lead_id:
            lead.broker_lead_id = their
            changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged["last_pull"] = row
            lead.payload = merged
            lead.save()
            updated += 1
        else:
            lead.save(update_fields=["last_pull_at"])
    return {"seen": seen, "matched": len(matched_pks), "updated": updated, "pages": 1}


def _irev_match(qs, row):
    """Aggancia un nostro lead a una riga della pull IREV: prima per
    broker_lead_id (leadUuid/uuid/externalId), poi email, poi telefono."""
    for key in ("leadUuid", "uuid", "lead_uuid", "externalId"):
        bid = str(row.get(key) or "").strip()
        if bid:
            lead = qs.filter(broker_lead_id=bid).first()
            if lead:
                return lead
    email = (row.get("email") or "").strip()
    if email:
        lead = qs.filter(email__iexact=email).first()
        if lead:
            return lead
    digits = "".join(ch for ch in str(row.get("phone") or "") if ch.isdigit())
    if len(digits) >= 9:
        return qs.filter(phone__endswith=digits[-9:]).first()
    return None


def sync_irev(broker, days=14, only_ids=None):
    """Pull stati IREV, allineata agli altri broker.
    - goal LEAD (goal_lead_uuid): aggiorna status/stage da `saleStatus`
      (no_answer, callback, not_interested...) via status_to_stage().
    - goal FTD (goal_ftd_uuid): marca i depositi come FTD.
    Aggancio per broker_lead_id (leadUuid) con fallback email/telefono.
    Se manca goal_lead_uuid fa solo la pull FTD (comportamento precedente)."""
    from . import irev
    lead_goal = getattr(broker, "goal_lead_uuid", "") or ""
    ftd_goal = getattr(broker, "goal_ftd_uuid", "") or ""
    if not lead_goal and not ftd_goal:
        return {"seen": 0, "matched": 0, "updated": 0, "pages": 0}
    now = datetime.now(dt_tz.utc)
    qs = Lead.for_broker(broker)
    stats = {"seen": 0, "matched": set(), "updated": 0}

    def _apply(lead, row, force_ftd):
        lead.last_pull_at = now
        changed = False
        sale = row.get("saleStatus") or row.get("status")
        new_stage = status_to_stage(sale)
        is_dep = force_ftd or new_stage == "ftd"
        if is_dep:
            if not lead.is_deposit:
                lead.is_deposit = True
                changed = True
            if lead.status != "FTD":
                lead.status = "FTD"
                changed = True
            if lead.stage != "ftd":
                lead.stage = "ftd"
                changed = True
        else:
            if sale and lead.status != str(sale)[:120]:
                lead.status = str(sale)[:120]
                changed = True
            if new_stage and lead.stage != "ftd" and lead.stage != new_stage:
                lead.stage = new_stage
                changed = True
        if changed:
            merged = dict(lead.payload or {})
            merged["last_pull"] = row
            lead.payload = merged
            lead.save()
            stats["updated"] += 1
        else:
            lead.save(update_fields=["last_pull_at"])

    def _pass(goal, force_ftd):
        for row in irev.pull_leads(broker, goal_type_uuid=goal, days=days):
            if not isinstance(row, dict):
                continue
            stats["seen"] += 1
            lead = _irev_match(qs, row)
            if lead is None or (only_ids is not None and lead.pk not in only_ids):
                continue
            stats["matched"].add(lead.pk)
            _apply(lead, row, force_ftd)

    if lead_goal:
        # Pass STATI: pull SENZA filtro goal. La pull filtrata per goal_lead
        # ritorna lo `saleStatus` CONGELATO al momento del push (sempre "new");
        # solo la pull senza goal porta lo stato CORRENTE (no answer, not
        # interested, depositor...) + gli FTD (saleStatus "depositor").
        _pass(None, force_ftd=False)
    if ftd_goal:
        _pass(ftd_goal, force_ftd=True)
    return {"seen": stats["seen"], "matched": len(stats["matched"]),
            "updated": stats["updated"], "pages": 1}


def sync_all_pullable():
    """Lancia la pull/sync per ogni broker attivo TrackBox + SPM Monster.
    IREV è escluso (stato via postback). Ritorna un riepilogo aggregato."""
    from .models import (TrackboxBroker, SpmMonsterBroker, GalassiaBroker,
                         IrevBroker, OpenAffBroker, GlobalTradeBroker, OneCryptBroker,
                         CpaForgeBroker)
    total = {"updated": 0, "matched": 0, "seen": 0, "brokers": 0, "errors": []}
    jobs = ([(b, sync_broker) for b in TrackboxBroker.objects.filter(is_active=True)]
            + [(b, sync_spmmonster) for b in SpmMonsterBroker.objects.filter(is_active=True)]
            + [(b, sync_galassia) for b in GalassiaBroker.objects.filter(is_active=True)]
            + [(b, sync_openaff) for b in OpenAffBroker.objects.filter(is_active=True)]
            + [(b, sync_globaltrade) for b in GlobalTradeBroker.objects.filter(is_active=True)]
            + [(b, sync_onecrypt) for b in OneCryptBroker.objects.filter(is_active=True)]
            + [(b, sync_cpaforge) for b in CpaForgeBroker.objects.filter(is_active=True)]
            + [(b, sync_irev) for b in IrevBroker.objects.filter(is_active=True, use_pull=True)])
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
    from .models import (SpmMonsterBroker, TrackboxBroker, GalassiaBroker,
                         IrevBroker, OpenAffBroker, GlobalTradeBroker, OneCryptBroker,
                         CpaForgeBroker)
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
            elif isinstance(b, GalassiaBroker):
                r = sync_galassia(b, only_ids=ids)
            elif isinstance(b, OpenAffBroker):
                r = sync_openaff(b, only_ids=ids)
            elif isinstance(b, GlobalTradeBroker):
                r = sync_globaltrade(b, only_ids=ids)
            elif isinstance(b, OneCryptBroker):
                r = sync_onecrypt(b, only_ids=ids)
            elif isinstance(b, CpaForgeBroker):
                r = sync_cpaforge(b, only_ids=ids)
            elif isinstance(b, IrevBroker) and getattr(b, "use_pull", False):
                r = sync_irev(b, only_ids=ids)
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
