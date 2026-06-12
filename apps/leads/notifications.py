"""Outbound notifications to Slack / Discord / Telegram / generic webhooks.

Fires on CRM events so the operator gets a real-time ping and can act on
hot leads within seconds. Failures are swallowed: a missed alert must
never block lead intake.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def _post_json(url, payload, timeout=8):
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(payload).encode("utf-8"),
    )
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def _post_form(url, payload, timeout=8):
    req = urllib.request.Request(
        url, method="POST",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def _format_text(event, payload):
    """Plain-text version of a notification, used by Slack/Telegram/generic."""
    title_map = {
        "new_lead": "🎯 Nuovo lead",
        "ftd": "💰 FTD",
        "sale_sold": "✅ Vendita venduta",
        "api_error": "⚠️ Errore API broker",
    }
    title = title_map.get(event, event)
    lines = [title]
    for k in ("name", "email", "phone", "country", "source", "product", "broker"):
        v = payload.get(k)
        if v:
            lines.append(f"• *{k.capitalize()}*: {v}")
    if payload.get("score") is not None:
        lines.append(f"• *Score*: {payload['score']}/100")
    if payload.get("error"):
        lines.append(f"• *Error*: {payload['error']}")
    return "\n".join(lines)


def send_to_webhook(hook, event, payload):
    """Dispatch one event to one configured NotificationWebhook.

    Returns (ok: bool, info: str). Errors are caught and reported, never
    re-raised — lead intake must keep working even if alerts fail.
    """
    try:
        if hook.kind == hook.KIND_SLACK:
            status = _post_json(hook.url, {
                "text": _format_text(event, payload),
            })
        elif hook.kind == hook.KIND_DISCORD:
            status = _post_json(hook.url, {
                "content": _format_text(event, payload).replace("*", "**"),
            })
        elif hook.kind == hook.KIND_TELEGRAM:
            # Telegram bot API expects chat_id + text on sendMessage.
            chat_id = hook.telegram_chat_id
            if not chat_id:
                return False, "missing chat_id"
            status = _post_form(hook.url, {
                "chat_id": chat_id,
                "text": _format_text(event, payload),
                "parse_mode": "Markdown",
            })
        else:  # generic
            status = _post_json(hook.url, {
                "event": event,
                "payload": payload,
            })
        ok = 200 <= status < 300
        return ok, f"HTTP {status}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        logger.warning("Webhook %s failed: %s", hook.pk, e)
        return False, str(e)[:120]


def fire(event, payload):
    """Notify every active webhook subscribed to `event` for this CRM."""
    from .models import NotificationWebhook

    for hook in NotificationWebhook.objects.filter(is_active=True):
        if hook.fires_for(event):
            send_to_webhook(hook, event, payload)
