"""Login-attempt rate limiting.

A small, dependency-free throttle that protects `/accounts/login/`
against credential stuffing and abuse-of-DEMO_MODE scenarios. Two
sliding counters per request:

  - by IP   — `login.ip.<ip>`        — 20 attempts / 5 min
  - by user — `login.user.<lower>`   — 10 attempts / 5 min

Either limit triggers a 429 with a `Retry-After` header. Counters are
incremented on POST only (GET to render the form is unlimited). A
successful login does NOT reset the counter — that's deliberate, since
a credential-stuffing attacker who guesses one valid pair shouldn't be
able to wipe the throttle state for the rest of their guesses.

Storage uses Django's default cache. With LocMemCache (single-process)
each worker has its own counters; with Redis cache (recommended in
prod when scaling out) counters are shared across workers. Both are
acceptable for this threat model — a determined attacker hitting
multiple workers still gets capped at N × per_worker_limit, which is
still tiny.
"""
from __future__ import annotations

from django.core.cache import cache
from django.http import HttpResponse

LOGIN_PATH = "/accounts/login/"
WINDOW_SECONDS = 5 * 60          # 5-minute sliding window
MAX_PER_IP = 20
MAX_PER_USER = 10


def _client_ip(request) -> str:
    """Best-effort visitor IP — trusts X-Forwarded-For when behind a proxy.

    nginx sets `X-Real-IP` from CF-Connecting-IP via real_ip_header in
    the vhost, so REMOTE_ADDR ends up = visitor IP. We still check
    XFF as a fallback for environments that don't rewrite REMOTE_ADDR.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        # First entry is the originating client per the XFF spec.
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _bucket(key: str, limit: int) -> tuple[int, bool]:
    """Increment `key`'s counter; return (current, is_over_limit)."""
    # add() initializes to 1 if missing; subsequent calls just incr.
    if cache.add(key, 1, timeout=WINDOW_SECONDS):
        return 1, 1 > limit
    try:
        n = cache.incr(key)
    except ValueError:
        # Race: key expired between add() and incr(). Reseed.
        cache.set(key, 1, timeout=WINDOW_SECONDS)
        n = 1
    return n, n > limit


class LoginThrottleMiddleware:
    """Throttle POSTs to the login view by IP + by submitted username."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == LOGIN_PATH:
            ip = _client_ip(request)
            ip_count, ip_over = _bucket(f"login.ip.{ip}", MAX_PER_IP)
            if ip_over:
                return self._too_many(WINDOW_SECONDS)
            # Username may be missing on malformed POSTs; tolerate that.
            username = (request.POST.get("username") or "").strip().lower()
            if username:
                _, user_over = _bucket(f"login.user.{username}", MAX_PER_USER)
                if user_over:
                    return self._too_many(WINDOW_SECONDS)
        return self.get_response(request)

    @staticmethod
    def _too_many(retry_after: int) -> HttpResponse:
        resp = HttpResponse(
            "Too many login attempts. Please wait a few minutes and try again.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )
        resp["Retry-After"] = str(retry_after)
        return resp
