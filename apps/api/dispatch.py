"""Webhook delivery helper.

Synchronous best-effort POST per matching subscription. For production
use this should be moved behind a task queue (Celery / RQ / arq) so a
slow subscriber doesn't slow down the dashboard request — Phase 17 or
beyond.

Usage from anywhere in the codebase:

    from apps.api.dispatch import dispatch_webhook
    dispatch_webhook("invoice.paid", {"id": invoice.id, "number": invoice.number, ...})

Each call:
- Picks every active Webhook whose `events` includes the event name.
- Serializes the payload deterministically (sorted keys, no whitespace).
- Signs with HMAC-SHA256 of the webhook's secret over the body.
- POSTs with `X-Apex-Signature: sha256=<hex>` and `X-Apex-Event: <name>`.
- Records a WebhookDelivery row regardless of success.

Errors during delivery (network, 5xx, timeouts) are logged + recorded
but never re-raised — webhook failures must not break the originating
request.
"""
from __future__ import annotations

import logging

from apps.api.models import Webhook, WebhookDelivery, serialize_event_payload

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 5


def dispatch_webhook(event: str, data: dict) -> int:
    """Dispatch one event to all matching active subscriptions.

    Returns the count of delivery attempts (success or failure).
    """
    matching = [
        w for w in Webhook.objects.filter(is_active=True)
        if w.matches(event)
    ]
    if not matching:
        return 0
    body = serialize_event_payload(event, data)
    delivered = 0
    for w in matching:
        _deliver(w, event=event, body=body, payload=data)
        delivered += 1
    return delivered


def _deliver(webhook: Webhook, *, event: str, body: bytes, payload: dict) -> None:
    """Single attempt — record + POST + record again."""
    delivery = WebhookDelivery.objects.create(
        webhook=webhook, event=event, payload=payload, attempts=1, status="pending",
    )
    try:
        # Lazy import so `requests` only loads when actually needed.
        # `urllib.request` is stdlib but doesn't expose a clean timeout
        # + custom-header API, so requests is worth the dep.
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            webhook.url, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Apex-Event": event,
                "X-Apex-Signature": f"sha256={webhook.sign(body)}",
                "User-Agent": "Apex-Webhook/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            delivery.status = "success" if 200 <= resp.status < 300 else "failed"
            delivery.response_code = resp.status
            try:
                delivery.response_body = resp.read(2048).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                delivery.response_body = ""
    except urllib.error.HTTPError as e:
        delivery.status = "failed"
        delivery.response_code = e.code
        try:
            delivery.response_body = e.read(2048).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            delivery.response_body = ""
    except Exception as e:  # noqa: BLE001
        delivery.status = "failed"
        delivery.response_body = str(e)[:2048]
        logger.warning("webhook delivery failed: %s → %s: %s", event, webhook.url, e)
    finally:
        delivery.save(update_fields=["status", "response_code", "response_body", "updated_at"])
