"""
Production settings — reads DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS from environment.
"""

import os
import urllib.parse

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = os.environ.get("DEBUG", "False") == "True"

SECRET_KEY = os.environ["SECRET_KEY"]

# ALLOWED_HOSTS — comma-separated list. Always includes the public demo
# host so a forgotten env var doesn't lock the demo out.
_env_hosts = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
ALLOWED_HOSTS = list({*_env_hosts})

# CSRF: Django 4+ requires explicit trusted origins for cross-host POST.
# Cloudflare terminates TLS so requests to origin still arrive over https.
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h and h != "*"
]

# WebSocket origin allow-list — Channels' AllowedHostsOriginValidator
# uses ALLOWED_HOSTS by default, so /ws/ upgrades from the demo domain
# work automatically once the host above is set.

# Behind Cloudflare + nginx — trust the X-Forwarded-Proto header so
# Django sees the request as HTTPS (otherwise the redirect-to-HTTPS
# loop kicks in even though the edge already terminated TLS).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# DATABASE_URL support (simple manual parsing; swap for dj-database-url if preferred).
# Recognised schemes:
#   postgres://, postgresql://   → django.db.backends.postgresql  (default)
#   mssql://, sqlserver://       → mssql                          (requires `--extra mssql`)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL environment variable is required in production.")

_parsed = urllib.parse.urlparse(DATABASE_URL)
_scheme = _parsed.scheme.lower()

if _scheme in ("mssql", "sqlserver"):
    # Microsoft SQL Server via Microsoft's official mssql-django backend.
    # Requires the `mssql` extra installed (`uv sync --extra mssql`) AND the
    # Microsoft ODBC Driver 18 present at the OS level. See README "Database"
    # section for installation steps.
    #
    # Driver override: query string `?driver=ODBC+Driver+17+for+SQL+Server`
    # lets you target an older ODBC driver if 18 isn't available. Default is
    # ODBC Driver 18 (the current Microsoft recommendation).
    #
    # TLS: SQL Server 2022 enforces encrypted connections by default. If your
    # server uses a self-signed cert (typical for a local docker image or an
    # on-prem instance without a public CA cert), append
    # `?trust_server_certificate=yes` to the URL to skip cert validation.
    _qs = urllib.parse.parse_qs(_parsed.query)
    _driver = _qs.get("driver", ["ODBC Driver 18 for SQL Server"])[0]
    _trust_cert = _qs.get("trust_server_certificate", ["no"])[0].lower() in ("1", "true", "yes")
    _options = {"driver": _driver}
    if _trust_cert:
        _options["extra_params"] = "TrustServerCertificate=yes"
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username,
            "PASSWORD": _parsed.password,
            "HOST": _parsed.hostname,
            "PORT": _parsed.port or 1433,
            "OPTIONS": _options,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path.lstrip("/"),
            "USER": _parsed.username,
            "PASSWORD": _parsed.password,
            "HOST": _parsed.hostname,
            "PORT": _parsed.port or 5432,
        }
    }

SECURE_HSTS_SECONDS = 31536000
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Iframe embedding allowlist — for the dashboardpack.com product preview
# iframe and similar partner placements. Defaults to no embedding (the
# strict `frame-ancestors 'none'` from base.py is preserved).
#
# X-Frame-Options is too coarse — its only multi-origin option (ALLOW-FROM)
# is deprecated and unsupported in Chrome/Safari. Modern browsers honor
# CSP `frame-ancestors`, which X-Frame-Options is superseded by when both
# are present. So when an allowlist is configured we drop the X-Frame
# header entirely and rely on CSP for the policy.
EMBED_PARENT_ORIGINS = [
    o.strip()
    for o in os.environ.get("EMBED_PARENT_ORIGINS", "").split(",")
    if o.strip()
]
if EMBED_PARENT_ORIGINS:
    MIDDLEWARE = [m for m in MIDDLEWARE if "XFrameOptions" not in m]  # noqa: F405
    SECURE_CSP = {  # noqa: F405
        **SECURE_CSP,  # noqa: F405
        "frame-ancestors": EMBED_PARENT_ORIGINS,
    }

# Demo mode — when DEMO_MODE=true is in the env, the login page shows
# a "Demo credentials" banner with a one-click autofill button. Off by
# default; we explicitly opt in for the public preview.
DEMO_MODE = os.environ.get("DEMO_MODE", "").lower() in ("1", "true", "yes")

# ── Prometheus metrics (opt-in) ─────────────────────────────────────
# Exposes /__metrics/ for Prometheus scraping. Auto-instruments DB
# queries, cache hits, request latency histograms, exceptions. No-op
# when METRICS_ENABLED is unset, so the endpoint is dormant by default
# (no perf cost, no exposure). Buyers running Prometheus / Grafana
# Cloud / Datadog flip one env var to enable.
# Requires `metrics` extra: `uv sync --extra metrics`.
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "").lower() in ("1", "true", "yes")
if METRICS_ENABLED:
    try:
        import django_prometheus  # noqa: F401

        # django-prometheus middleware bookends every request — must be
        # FIRST and LAST in the MIDDLEWARE list so latency measurement
        # captures every other middleware's overhead too.
        INSTALLED_APPS = [*INSTALLED_APPS, "django_prometheus"]  # noqa: F405
        MIDDLEWARE = [  # noqa: F405
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
            *MIDDLEWARE,  # noqa: F405
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ]
    except ImportError:
        # `metrics` extra not installed — skip wiring; the endpoint will 404.
        METRICS_ENABLED = False


# ── Sentry (opt-in) ─────────────────────────────────────────────────
# Capture uncaught exceptions in prod for triage. No-op when SENTRY_DSN
# is unset, so dev + tests + the demo-without-Sentry path all work.
# Requires `sentry` extra: `uv sync --extra sentry`.
SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            # Performance trace sampling — keep low to avoid quota burn on
            # a public demo. Bump to 1.0 in private debug sessions.
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE", "0.05")),
            send_default_pii=False,
            environment=os.environ.get("SENTRY_ENV", "production"),
            release=os.environ.get("SENTRY_RELEASE") or None,
        )
    except ImportError:
        # `sentry` extra not installed — leave init unwired and continue.
        pass

# Channels — upgrade to Redis-backed channel layer if REDIS_URL is set.
# Otherwise fall back to the in-memory layer from base.py (single-process
# only, but lets the app boot without Redis if you don't need realtime).
REDIS_URL = os.environ.get("REDIS_URL")

# Live scores — aggregatore multi-fonte
FOOTBALL_DATA_API_TOKEN = os.environ.get("FOOTBALL_DATA_API_TOKEN", "")
API_FOOTBALL_TOKEN = os.environ.get("API_FOOTBALL_TOKEN", "")
ALLSPORTS_API_TOKEN = os.environ.get("ALLSPORTS_API_TOKEN", "")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        },
    }
    # Share Django's cache backend with Redis too — so the login-throttle
    # counters survive worker restarts and are accurate across processes.
    # Use a different Redis DB if you want to isolate from the channel
    # layer pub/sub (channels-redis prefixes its keys, so collisions are
    # extremely unlikely either way).
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "apex",
        },
    }
