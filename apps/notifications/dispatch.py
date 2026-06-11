"""Central notification dispatcher.

Phase 13 introduces `notify(user, category, ...)` as the canonical entry
point. It honors `NotificationPreference` per channel:

  - in_app channel  → creates a Notification row (visible in bell + list)
  - email channel   → sends a transactional email via the configured backend
  - push channel    → fires a Web Push (when a PushSubscription is registered)

The legacy per-event helpers (`notify_invoice_sent`, etc.) still exist
for back-compat — they now route through `notify()` so preference
checks apply uniformly. New code should call `notify()` directly.
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from apps.notifications.models import (
    KIND_TO_CATEGORY,
    Notification,
    get_effective_pref,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def notify(
    *,
    recipient,
    category: str,
    title: str,
    body: str = "",
    target_url: str = "",
    kind: str = "",
    actor=None,
) -> Notification | None:
    """Send a notification to a single user, honoring their preferences.

    Returns the created Notification if the in_app channel is on for this
    (user, category); else None. Email + push channels fire as side
    effects when their respective preferences are enabled and channels
    are configured (real push send is deferred — see
    apps.notifications.push when added).
    """
    if recipient is None or not getattr(recipient, "is_authenticated", True):
        return None

    in_app = get_effective_pref(recipient, category, "in_app")
    email = get_effective_pref(recipient, category, "email")
    push = get_effective_pref(recipient, category, "push")

    notification = None
    if in_app:
        notification = Notification.objects.create(
            recipient=recipient,
            actor=actor,
            category=category,
            kind=kind or category,
            title=title,
            body=body,
            url=target_url,
        )
        # Realtime fan-out — push the new row to any open WebSocket
        # tabs the recipient has. Best-effort: never let a layer error
        # break the request that triggered the notification.
        try:
            from apps.realtime.dispatch import (
                push_notification,
                push_unread_count,
            )
            push_notification(recipient.id, {
                "id": notification.id,
                "title": notification.title,
                "body": notification.body,
                "url": notification.url,
                "category": notification.category,
                "kind": notification.kind,
                "created_at": notification.created_at.isoformat(),
            })
            unread = Notification.objects.filter(
                recipient=recipient, read_at__isnull=True,
            ).count()
            push_unread_count(recipient.id, unread)
        except Exception:  # noqa: BLE001
            logger.exception("notify(): realtime fan-out failed")

    if email and recipient.email:
        try:
            send_mail(
                subject=title,
                message=body or title,
                from_email=None,
                recipient_list=[recipient.email],
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001 — email backend errors must not break the request
            logger.exception("notify(): email send failed for %s", recipient.email)

    if push:
        try:
            from apps.notifications.push import send_push_to_user
            send_push_to_user(recipient, title=title, body=body, url=target_url)
        except ImportError:
            # Push module not yet installed — fine, in_app/email still fired.
            pass
        except Exception:  # noqa: BLE001
            logger.exception("notify(): push send failed for user_id=%s", recipient.pk)

    return notification


def notify_many(
    *,
    recipients,
    category: str,
    title: str,
    body: str = "",
    target_url: str = "",
    kind: str = "",
    actor=None,
) -> int:
    """Fan out a single notification across many users.

    Returns the count of in_app notifications actually created (i.e.
    recipients who hadn't disabled the in_app channel for this category).
    """
    count = 0
    for user in recipients:
        n = notify(
            recipient=user, category=category, title=title, body=body,
            target_url=target_url, kind=kind, actor=actor,
        )
        if n is not None:
            count += 1
    return count


def _staff_recipients():
    return User.objects.filter(is_staff=True, is_active=True)


# ── Legacy per-event helpers (Phase 4c) ──────────────────────────────
# Forward to notify_many() with the right category from KIND_TO_CATEGORY,
# so preference checks now apply.


def _legacy_fanout(kind: str, *, title: str, body: str = "", url: str = "") -> None:
    notify_many(
        recipients=_staff_recipients(),
        category=KIND_TO_CATEGORY.get(kind, "system"),
        kind=kind,
        title=title,
        body=body,
        target_url=url,
    )


def notify_invoice_sent(invoice) -> None:
    _legacy_fanout(
        "invoice_sent",
        title=f"Invoice {invoice.number} sent",
        body=f"to {invoice.customer.name}",
        url=invoice.get_absolute_url(),
    )


def notify_invoice_paid(invoice) -> None:
    _legacy_fanout(
        "invoice_paid",
        title=f"Invoice {invoice.number} marked paid",
        body=f"${invoice.total} from {invoice.customer.name}",
        url=invoice.get_absolute_url(),
    )


def notify_invoice_void(invoice) -> None:
    _legacy_fanout(
        "invoice_void",
        title=f"Invoice {invoice.number} voided",
        url=invoice.get_absolute_url(),
    )


def notify_order_placed(order) -> None:
    _legacy_fanout(
        "order_placed",
        title=f"New order {order.number or f'#{order.pk}'}",
        body=f"from {order.customer.name}",
        url=f"/orders/{order.pk}/",
    )


def notify_new_mail(message) -> None:
    """Single-recipient: only the message recipient gets a notification."""
    sender_label = message.sender.get_full_name() or message.sender.username
    notify(
        recipient=message.recipient,
        category="mention",
        kind="new_mail",
        actor=message.sender,
        title=f"{sender_label}: {message.subject}",
        body=message.body[:140],
        target_url=f"/mail/{message.pk}/",
    )


def notify_new_chat(chat_message) -> None:
    """Single-recipient: only the chat recipient gets a notification."""
    sender_label = chat_message.sender.get_full_name() or chat_message.sender.username
    notify(
        recipient=chat_message.recipient,
        category="mention",
        kind="new_chat",
        actor=chat_message.sender,
        title=sender_label,
        body=chat_message.body[:140],
        target_url=f"/chat/{chat_message.sender_id}/",
    )
