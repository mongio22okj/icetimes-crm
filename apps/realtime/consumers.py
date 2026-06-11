"""WebSocket consumers for realtime surfaces.

We ship two consumers in Phase 14:

  - `NotificationConsumer` — per-user channel. Server-side code calls
    `push_notification(user, payload)` (from `apps.realtime.dispatch`)
    and the client sees it instantly without polling.
  - `PresenceConsumer` — global "who's online right now" channel.
    Tracks counts via the channel layer's group membership, broadcasts
    a delta any time a connection opens or closes.

Both consumers are JSON-only and reject anonymous connections so we
don't have to think about anonymous identity. They use Channels'
`AsyncJsonWebsocketConsumer` so each consumer can `await` Django ORM
calls with `database_sync_to_async`.

Channel groups:
  - `notify.user.<id>`     — per-user fan-out
  - `presence.global`      — global presence broadcasts
"""
from __future__ import annotations

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


def user_group(user_id: int) -> str:
    return f"notify.user.{user_id}"


PRESENCE_GROUP = "presence.global"


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Per-user notification feed.

    Client connects to `/ws/notifications/`. On connect we join the
    user's group; server-side `push_notification(user, payload)` calls
    fan-out via `group_send`.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.group = user_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    # ── Group event handlers ──────────────────────────────────────────
    # `dispatch.push_notification()` sends `{"type": "notify.message",
    # "payload": {...}}`. Channels routes that type to this method.

    async def notify_message(self, event):
        await self.send_json({"event": "notification", "data": event["payload"]})

    async def notify_count(self, event):
        await self.send_json({"event": "unread_count", "count": event["count"]})


class PresenceConsumer(AsyncJsonWebsocketConsumer):
    """Global "who's online" channel.

    Maintains presence by joining/leaving `presence.global`. On each
    transition we broadcast the new count to everyone in the group.
    Counting is done via the layer's per-process group registry; this
    is approximate at multi-process scale but fine for the demo.
    """

    # Module-level set of currently-connected channel names (per-process).
    # The in-memory channel layer keeps a list internally too; we keep
    # our own so prod-style Redis layers (no listing API) still work.
    _connected: set[str] = set()

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user_id = user.id
        self.username = user.get_username()
        await self.channel_layer.group_add(PRESENCE_GROUP, self.channel_name)
        PresenceConsumer._connected.add(self.channel_name)
        await self.accept()
        await self._broadcast_state(joined=self.username)

    async def disconnect(self, code):
        PresenceConsumer._connected.discard(self.channel_name)
        if hasattr(self, "username"):
            await self._broadcast_state(left=self.username)
        await self.channel_layer.group_discard(PRESENCE_GROUP, self.channel_name)

    async def _broadcast_state(self, *, joined: str | None = None,
                               left: str | None = None) -> None:
        await self.channel_layer.group_send(
            PRESENCE_GROUP,
            {
                "type": "presence.update",
                "count": len(PresenceConsumer._connected),
                "joined": joined,
                "left": left,
            },
        )

    async def presence_update(self, event):
        await self.send_json({
            "event": "presence",
            "count": event["count"],
            "joined": event.get("joined"),
            "left": event.get("left"),
        })


@database_sync_to_async
def _resolve_user(user_id: int):
    """Defensive ORM helper kept here so tests can patch it cleanly."""
    from django.contrib.auth import get_user_model
    return get_user_model().objects.filter(pk=user_id).first()
