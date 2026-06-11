"""Sync tests for the realtime dispatch helpers + notification fan-out."""
from __future__ import annotations

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.tests.factories import UserFactory
from apps.notifications.dispatch import notify
from apps.realtime.consumers import user_group
from apps.realtime.dispatch import push_notification, push_unread_count


@pytest.mark.django_db
def test_push_notification_lands_in_group():
    layer = get_channel_layer()
    # Fake-subscribe a channel to the group so we can drain it.
    test_channel = "test.channel.notify"
    async_to_sync(layer.group_add)(user_group(42), test_channel)
    push_notification(42, {"title": "Hi"})
    msg = async_to_sync(layer.receive)(test_channel)
    assert msg["type"] == "notify.message"
    assert msg["payload"] == {"title": "Hi"}
    async_to_sync(layer.group_discard)(user_group(42), test_channel)


@pytest.mark.django_db
def test_push_unread_count_lands_in_group():
    layer = get_channel_layer()
    test_channel = "test.channel.count"
    async_to_sync(layer.group_add)(user_group(99), test_channel)
    push_unread_count(99, 3)
    msg = async_to_sync(layer.receive)(test_channel)
    assert msg == {"type": "notify.count", "count": 3}
    async_to_sync(layer.group_discard)(user_group(99), test_channel)


@pytest.mark.django_db
def test_notify_dispatcher_fans_out_to_realtime_layer():
    """End-to-end: calling notify() should produce both a Notification
    row and a channel-layer message routed to the recipient's group."""
    user = UserFactory(is_staff=True)
    layer = get_channel_layer()
    test_channel = "test.channel.e2e"
    async_to_sync(layer.group_add)(user_group(user.id), test_channel)

    n = notify(
        recipient=user, category="system", title="Hello",
        body="world", target_url="/x/",
    )
    assert n is not None

    # First message: the notification payload.
    msg1 = async_to_sync(layer.receive)(test_channel)
    assert msg1["type"] == "notify.message"
    assert msg1["payload"]["title"] == "Hello"
    assert msg1["payload"]["body"] == "world"
    assert msg1["payload"]["url"] == "/x/"

    # Second message: refreshed unread count (= 1 since we just created it).
    msg2 = async_to_sync(layer.receive)(test_channel)
    assert msg2 == {"type": "notify.count", "count": 1}

    async_to_sync(layer.group_discard)(user_group(user.id), test_channel)


@pytest.mark.django_db
def test_dispatch_helpers_no_op_when_layer_returns_none(monkeypatch):
    """If get_channel_layer() returns None (no layer configured),
    dispatch helpers must silently no-op rather than raise."""
    import apps.realtime.dispatch as mod
    monkeypatch.setattr(mod, "get_channel_layer", lambda: None)
    # Should not raise.
    mod.push_notification(1, {"x": 1})
    mod.push_unread_count(1, 0)
