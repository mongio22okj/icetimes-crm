"""WebSocket URL routing for the realtime app."""
from django.urls import path

from apps.realtime import consumers

websocket_urlpatterns = [
    path("ws/notifications/", consumers.NotificationConsumer.as_asgi()),
    path("ws/presence/", consumers.PresenceConsumer.as_asgi()),
]
