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
