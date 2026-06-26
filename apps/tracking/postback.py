"""Ricevitore postback broker→CRM (TrackBox).

Il broker richiama questo endpoint (GET) su eventi Lead/FTD con:
    ?token=<LEADS_POSTBACK_TOKEN>&lead_id={affclickid}&status=…&isDeposit=…

Aggancio: `lead_id` = il NOSTRO `click_id` (= affclickid inviato al push).
Update-only: NON crea lead orfani per id sconosciuti.
"""
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Lead


def _first(data, *keys):
    for key in keys:
        val = data.get(key)
        if val not in (None, "", "null"):
            return val
    return None


def _truthy(value) -> bool:
    return str(value).strip().lower() in {
        "1", "true", "yes", "y", "deposit", "ftd", "depositor", "depositors"}


def _amount_positive(data, *keys) -> bool:
    for key in keys:
        raw = data.get(key)
        if raw in (None, ""):
            continue
        try:
            if float(str(raw).replace(",", ".")) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


@csrf_exempt
def postback(request):
    expected = getattr(settings, "LEADS_POSTBACK_TOKEN", "") or ""
    data = dict(request.GET.items())
    if request.method == "POST":
        data.update(request.POST.items())

    supplied = data.get("token") or request.headers.get("X-Postback-Token", "")
    if not expected:
        return JsonResponse(
            {"ok": False, "error": "postback token not configured on server"},
            status=503)
    if not hmac.compare_digest(str(supplied), str(expected)):
        return JsonResponse({"ok": False, "error": "invalid token"}, status=403)
    data.pop("token", None)

    # Aggancio per il nostro click_id (lead_id={affclickid}); fallback su
    # broker_lead_id se il broker manda il suo id interno.
    key = str(_first(data, "lead_id", "leadId", "affclickid", "click_id",
                     "clickid") or "")
    broker_key = str(_first(data, "customerID", "customerId", "uniqueid",
                            "uniqueId") or "")

    lead = None
    if key:
        lead = Lead.objects.filter(click_id=key).first()
    if lead is None and broker_key:
        lead = Lead.objects.filter(broker_lead_id=broker_key).first()
    if lead is None and key:
        lead = Lead.objects.filter(broker_lead_id=key).first()
    if lead is None:
        # Niente lead da agganciare: non creiamo orfani, accettiamo e basta.
        return JsonResponse({"ok": True, "ignored": True,
                             "reason": "unknown lead"})

    changed = False
    status = _first(data, "status", "termine", "saleStatus", "callStatus",
                    "statusName")
    if status and lead.status != str(status)[:120]:
        lead.status = str(status)[:120]
        changed = True

    is_dep = (_truthy(_first(data, "isDeposit", "isDeposited", "deposit",
                             "ftd", "a.D"))
              or str(status or "").strip().lower() in {"ftd", "deposit", "depositor"}
              or _amount_positive(data, "pagamento", "depositi", "amount"))
    if is_dep and not lead.is_deposit:
        lead.is_deposit = True
        changed = True

    if broker_key and not lead.broker_lead_id:
        lead.broker_lead_id = broker_key
        changed = True

    if not lead.event_at:
        lead.event_at = timezone.now()

    payload = dict(lead.payload or {})
    payload["last_postback"] = data
    lead.payload = payload
    lead.save()

    return JsonResponse({
        "ok": True, "id": lead.pk, "status": lead.status,
        "is_deposit": lead.is_deposit, "changed": changed,
    })
