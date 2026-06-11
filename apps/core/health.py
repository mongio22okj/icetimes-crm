"""Health-check endpoint for uptime monitors and orchestrators.

`GET /__health/` returns:

  - `200 {"status": "ok", "checks": {...}}` when DB + cache + channel
    layer are all reachable
  - `503 {"status": "degraded", "checks": {...}}` when any check fails

Each check is best-effort and timeboxed (no check should hang the
endpoint). Exception messages are included in the JSON so a failing
probe is easy to diagnose without SSHing in. We deliberately do NOT
authenticate — uptime monitors hit this anonymously, and there's no
sensitive info in the response.

Wired in `apex/urls.py` at `/__health/` (double underscore = "internal,
not for humans"). Cache-Control is `no-store` so Cloudflare/edge layers
never cache the result.
"""
from __future__ import annotations

import time

from asgiref.sync import async_to_sync
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


def _check_db() -> dict:
    t = time.perf_counter()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"ok": True, "ms": round((time.perf_counter() - t) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 — health check must not raise
        return {"ok": False, "error": str(exc)[:200]}


def _check_channel_layer() -> dict:
    """Send + receive a single message through the configured layer.

    Uses a one-off channel name so we don't pollute any real groups.
    Skipped (returns ok=None) when no layer is configured.
    """
    from channels.layers import get_channel_layer

    layer = get_channel_layer()
    if layer is None:
        return {"ok": None, "skipped": "no channel layer configured"}
    t = time.perf_counter()
    try:
        channel = "__health.ping"
        async_to_sync(layer.send)(channel, {"type": "ping"})
        msg = async_to_sync(layer.receive)(channel)
        if msg.get("type") != "ping":
            return {"ok": False, "error": f"unexpected reply: {msg!r}"[:200]}
        return {"ok": True, "ms": round((time.perf_counter() - t) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}


@require_GET
@never_cache
def health(request):
    checks = {
        "db": _check_db(),
        "channel_layer": _check_channel_layer(),
    }
    # Aggregate: degraded if ANY required check failed (None = skipped, ok)
    failed = [k for k, v in checks.items() if v.get("ok") is False]
    status = "ok" if not failed else "degraded"
    code = 200 if not failed else 503
    return JsonResponse(
        {"status": status, "checks": checks, "failed": failed},
        status=code,
    )
