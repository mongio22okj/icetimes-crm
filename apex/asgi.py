"""ASGI config for apex project.

Routes HTTP through Django's normal stack and WebSocket through the
realtime app's URL router. Auth is handled by `AuthMiddlewareStack`
so consumers see `scope["user"]` populated from the session cookie.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apex.settings.prod")

# Resolve the Django HTTP application before importing anything that
# touches the ORM — AuthMiddlewareStack imports django.contrib.auth.
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    ),
})

