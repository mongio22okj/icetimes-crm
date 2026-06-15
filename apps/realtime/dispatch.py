"""Server-side helpers for pushing events to WebSocket consumers.

These are sync wrappers around `channel_layer.group_send` so any view,
signal handler, or management command can fan out without thinking
about async. They no-op when no channel layer is configured (rare,
but keeps the test harness from blowing up).
"""
from __future__ import annotations

from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.realtime.consumers import LEADS_FEED_GROUP, user_group


def broadcast_new_lead(payload: dict[str, Any]) -> None:
    """Spinge un nuovo lead a tutto lo staff connesso (feed globale)."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        LEADS_FEED_GROUP,
        {"type": "lead.new", "payload": payload},
    )


def push_notification(user_id: int, payload: dict[str, Any]) -> None:
    """Send a notification payload to all sockets owned by `user_id`."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        user_group(user_id),
        {"type": "notify.message", "payload": payload},
    )


def push_unread_count(user_id: int, count: int) -> None:
    """Update the bell badge across all open tabs for a user."""
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        user_group(user_id),
        {"type": "notify.count", "count": count},
    )
