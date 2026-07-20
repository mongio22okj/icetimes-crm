"""Invia ogni nuovo lead a un Google Sheet (webhook Apps Script), fire-and-forget.
Chiamato dallo stesso punto di telegram_notify.notify_new_lead (dopo il push),
cosi' include autologin ed esito. No-op se LEAD_SHEETS_WEBHOOK_URL non e' settata."""
import json
import os
import threading
import urllib.request


def _conf():
    return (os.environ.get("LEAD_SHEETS_WEBHOOK_URL", ""),
            os.environ.get("LEAD_SHEETS_WEBHOOK_SECRET", ""))


# Stessi colori usati nella tabella Lead del CRM (templates/tracking/lead_list.html),
# convertiti da rgba() semi-trasparente su sfondo bianco a hex piatto (Sheets non
# supporta la trasparenza sulle celle). Priorita': duplicato > FTD pagata > FTD > in attesa.
_COLOR_DUPLICATE = "#FDE3E3"   # rosso   (bg-red-500/15)
_COLOR_FTD_PAID = "#ACE3FC"    # azzurro (rgba(56,189,248,.42))
_COLOR_FTD = "#A7E8BF"         # verde   (rgba(34,197,94,.40))
_COLOR_PENDING = "#FDEBA1"     # giallo  (rgba(250,204,21,.40))


def _row_color(lead):
    if lead.is_duplicate:
        return _COLOR_DUPLICATE
    if lead.is_deposit:
        return _COLOR_FTD_PAID if getattr(lead, "ftd_paid", False) else _COLOR_FTD
    if (lead.payload or {}).get("deposit_pending"):
        return _COLOR_PENDING
    return None


def lead_to_row(lead, result=None):
    try:
        broker = lead.broker
    except Exception:  # noqa: BLE001
        broker = None
    push_ok = None
    if result is not None:
        push_ok = bool(result.get("success"))
    return {
        "created_at": lead.created_at.strftime("%d/%m/%Y %H:%M") if lead.created_at else "",
        "firstname": lead.firstname or "",
        "lastname": lead.lastname or "",
        "email": lead.email or "",
        "phone": lead.phone or "",
        "country": lead.country or "",
        "funnel": getattr(broker, "funnel", "") or "",
        "broker": getattr(broker, "name", "") or "",
        "broker_kind": getattr(broker, "kind_label", "") or "",
        "status": lead.status or "",
        "is_deposit": bool(lead.is_deposit),
        "click_id": lead.click_id or "",
        "ip": str(lead.ip) if lead.ip else "",
        "login_url": (lead.payload or {}).get("login_url") or "",
        "push_ok": push_ok,
        "row_color": _row_color(lead),
    }


def notify_sheets(lead, result=None):
    url, secret = _conf()
    if not url or not secret:
        return
    payload = {"secret": secret, "leads": [lead_to_row(lead, result)]}
    data = json.dumps(payload).encode("utf-8")

    def _send():
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=15).read()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=_send, daemon=True).start()
