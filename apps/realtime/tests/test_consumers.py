"""Async tests for the WebSocket consumers.

Uses Channels' WebsocketCommunicator which speaks ASGI directly — no
HTTP server required. The in-memory channel layer (settings default
in dev/test) handles fan-out so we don't need Redis.
"""
from __future__ import annotations

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.realtime.consumers import (
    NotificationConsumer,
    PresenceConsumer,
    user_group,
)


@database_sync_to_async
def _make_user(**kwargs):
    User = get_user_model()
    return User.objects.create_user(**kwargs)


def _user_communicator(consumer_cls, path, user):
    """WebsocketCommunicator + scope[user] preset to bypass middleware."""
    comm = WebsocketCommunicator(consumer_cls.as_asgi(), path)
    comm.scope["user"] = user
    return comm


# ── NotificationConsumer ──────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_consumer_rejects_anonymous():
    comm = _user_communicator(NotificationConsumer,
                              "/ws/notifications/", AnonymousUser())
    connected, code = await comm.connect()
    assert connected is False
    # The consumer closes with custom code 4401 to mean "anonymous, won't retry".
    assert code == 4401


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_consumer_accepts_authenticated_user():
    user = await _make_user(username="alice", email="a@x.io",
                            password="pw", email_verified_at=None)
    comm = _user_communicator(NotificationConsumer,
                              "/ws/notifications/", user)
    connected, _ = await comm.connect()
    assert connected is True
    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_consumer_receives_group_message():
    user = await _make_user(username="bob", email="b@x.io", password="pw")
    comm = _user_communicator(NotificationConsumer,
                              "/ws/notifications/", user)
    connected, _ = await comm.connect()
    assert connected is True

    # Push via the group as the dispatcher would.
    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    await layer.group_send(
        user_group(user.id),
        {
            "type": "notify.message",
            "payload": {"id": 1, "title": "Hi", "body": "there",
                        "url": "/x/", "category": "system",
                        "kind": "test", "created_at": "2026-04-30T00:00:00Z"},
        },
    )
    msg = await comm.receive_json_from(timeout=2)
    assert msg["event"] == "notification"
    assert msg["data"]["title"] == "Hi"
    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_consumer_receives_unread_count():
    user = await _make_user(username="carol", email="c@x.io", password="pw")
    comm = _user_communicator(NotificationConsumer,
                              "/ws/notifications/", user)
    await comm.connect()

    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    await layer.group_send(
        user_group(user.id),
        {"type": "notify.count", "count": 7},
    )
    msg = await comm.receive_json_from(timeout=2)
    assert msg == {"event": "unread_count", "count": 7}
    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_notification_isolated_per_user():
    """User A's group_send must NOT reach user B's socket."""
    a = await _make_user(username="ua", email="ua@x.io", password="pw")
    b = await _make_user(username="ub", email="ub@x.io", password="pw")
    ca = _user_communicator(NotificationConsumer, "/ws/notifications/", a)
    cb = _user_communicator(NotificationConsumer, "/ws/notifications/", b)
    await ca.connect()
    await cb.connect()

    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    await layer.group_send(
        user_group(a.id),
        {"type": "notify.message", "payload": {"title": "for-a"}},
    )
    msg_a = await ca.receive_json_from(timeout=2)
    assert msg_a["data"]["title"] == "for-a"
    # B should see nothing — receive_nothing() returns True if empty.
    assert await cb.receive_nothing(timeout=0.5) is True
    await ca.disconnect()
    await cb.disconnect()


# ── PresenceConsumer ──────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_presence_rejects_anonymous():
    comm = _user_communicator(PresenceConsumer, "/ws/presence/",
                              AnonymousUser())
    connected, code = await comm.connect()
    assert connected is False
    assert code == 4401


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_presence_broadcasts_count_and_join_on_connect():
    # Reset the per-process state so prior tests don't bleed into the count.
    PresenceConsumer._connected.clear()
    user = await _make_user(username="zoe", email="z@x.io", password="pw")
    comm = _user_communicator(PresenceConsumer, "/ws/presence/", user)
    connected, _ = await comm.connect()
    assert connected is True
    msg = await comm.receive_json_from(timeout=2)
    assert msg["event"] == "presence"
    assert msg["count"] == 1
    assert msg["joined"] == "zoe"
    await comm.disconnect()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_presence_count_reflects_two_connected_clients():
    PresenceConsumer._connected.clear()
    a = await _make_user(username="pa", email="pa@x.io", password="pw")
    b = await _make_user(username="pb", email="pb@x.io", password="pw")
    ca = _user_communicator(PresenceConsumer, "/ws/presence/", a)
    cb = _user_communicator(PresenceConsumer, "/ws/presence/", b)

    await ca.connect()
    msg_first = await ca.receive_json_from(timeout=2)
    assert msg_first["count"] == 1

    await cb.connect()
    # A sees the join broadcast (count=2, joined=pb).
    msg_a_join = await ca.receive_json_from(timeout=2)
    assert msg_a_join["count"] == 2
    assert msg_a_join["joined"] == "pb"
    # B's own connect-ack carries the same count.
    msg_b_join = await cb.receive_json_from(timeout=2)
    assert msg_b_join["count"] == 2

    await cb.disconnect()
    msg_a_leave = await ca.receive_json_from(timeout=2)
    assert msg_a_leave["count"] == 1
    assert msg_a_leave["left"] == "pb"
    await ca.disconnect()
