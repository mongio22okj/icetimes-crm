"""Notifica Telegram per ogni nuovo lead (fire-and-forget, mai blocca la cattura)."""
import os
import threading
import urllib.parse
import urllib.request


def _conf():
    return (os.environ.get("LEAD_TG_BOT_TOKEN", ""),
            os.environ.get("LEAD_TG_CHAT_ID", ""))


def notify_new_lead(lead):
    token, chat = _conf()
    if not token or not chat:
        return
    nome = ((lead.firstname or "") + " " + (lead.lastname or "")).strip() or "—"
    try:
        broker = lead.broker_name or "—"
    except Exception:  # noqa: BLE001
        broker = "—"
    text = ("🆕 <b>Nuovo lead</b> — %s\n📧 %s\n📞 %s\n🌍 %s\n🔗 Broker: <b>%s</b>") % (
        nome, lead.email or "—", lead.phone or "—", lead.country or "—", broker)
    data = urllib.parse.urlencode({
        "chat_id": chat, "parse_mode": "HTML",
        "text": text, "disable_web_page_preview": "true",
    }).encode()
    url = "https://api.telegram.org/bot%s/sendMessage" % token

    def _send():
        try:
            urllib.request.urlopen(url, data=data, timeout=10).read()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=_send, daemon=True).start()
