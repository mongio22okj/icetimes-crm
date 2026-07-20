"""Notifica Telegram per ogni nuovo lead (fire-and-forget). Inviata DOPO il
push, cosi include autologin ed esito routing."""
import html
import os
import threading
import urllib.parse
import urllib.request


def _conf():
    return (os.environ.get("LEAD_TG_BOT_TOKEN", ""),
            os.environ.get("LEAD_TG_CHAT_ID", ""))


def _e(v):
    return html.escape(str(v if v not in (None, "") else "—"))


def notify_new_lead(lead, result=None):
    token, chat = _conf()
    if not token or not chat:
        return
    nome = ((lead.firstname or "") + " " + (lead.lastname or "")).strip() or "—"
    try:
        broker = lead.broker
    except Exception:  # noqa: BLE001
        broker = None
    broker_name = getattr(broker, "name", "") or "—"
    api_src = getattr(broker, "kind_label", "") or "—"
    funnel = getattr(broker, "funnel", "") or "—"
    autologin = (lead.payload or {}).get("login_url") or ""
    status = lead.status or (lead.get_stage_display() if hasattr(lead, "get_stage_display") else "")

    # Un 504 / timeout NON è un rifiuto: il gateway del broker non aspetta la
    # risposta ma il lead viene comunque registrato (confermato dal broker
    # stylishwnt). Va segnalato come timeout, non come "PUSH FALLITO".
    err = str((result or {}).get("error") or "")
    is_timeout = (result is not None and not result.get("success")
                  and ("504" in err or "timeout" in err.lower()
                       or "time out" in err.lower() or "timed out" in err.lower()))
    failed = result is not None and not result.get("success") and not is_timeout

    if result is not None:
        ok = bool(result.get("success"))
        if ok:
            routing = "✅ %s — OK" % _e(broker_name)
        elif is_timeout:
            routing = ("⏳ %s — timeout/504 (di norma il lead è registrato lato "
                       "broker, verifica via pull)" % _e(broker_name))
        else:
            routing = "❌ %s — %s" % (_e(broker_name), _e(err[:120] or "rifiutato"))
    else:
        routing = ("✅ %s — OK" % _e(broker_name)) if autologin else ("⏳ %s" % _e(broker_name))

    if failed:
        header = "🚨 <b>PUSH FALLITO — lead NON inviato al broker</b>"
    elif is_timeout:
        header = "⏳ <b>NUOVO LEAD — timeout broker (504), lead registrato</b>"
    else:
        header = "🆕 <b>NUOVO LEAD</b>"

    lines = [
        header,
        "👤 <b>%s</b>" % _e(nome),
        "📧 %s" % _e(lead.email),
        "📞 %s" % _e(lead.phone),
        "🌍 GEO: %s" % _e(lead.country),
        "🎯 Funnel: %s" % _e(funnel),
        "🔌 Broker: <b>%s</b> (%s)" % (_e(broker_name), _e(api_src)),
        "📊 Status: %s" % _e(status),
        "🆔 Click ID: %s" % _e(lead.click_id),
        "🌐 IP: %s" % _e(str(lead.ip) if lead.ip else "—"),
    ]
    if autologin:
        lines.append("🔗 Autologin: <a href=\"%s\">%s</a>"
                     % (html.escape(autologin, quote=True), _e(autologin)))
    lines.append("🧭 %s" % routing)
    text = "\n".join(lines)

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
