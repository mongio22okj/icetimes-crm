"""
Base Django settings for apex project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECRET_KEY must be set by the importing settings module (dev.py / prod.py)
SECRET_KEY = None

DEBUG = False

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    # Daphne must come first so its `runserver` (ASGI-aware) replaces
    # Django's WSGI-only runserver. Channels relies on it for dev.
    "daphne",
    # Apex admin theme — must come BEFORE django.contrib.admin so the project
    # template loader picks up templates/admin/ overrides and apex_admin
    # templatetags are registered.
    "apex.admin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.forms",
    "channels",
    "apps.core",
    "apps.accounts",
    "apps.api",
    "apps.leads",
    "apps.notifications",
    "apps.organizations",
    "apps.products",
    "apps.realtime",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.SiteGateMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.LockedSessionMiddleware",
    "apps.accounts.middleware.SessionMetadataMiddleware",
    "apps.accounts.throttle.LoginThrottleMiddleware",
    "apps.organizations.middleware.OrganizationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "apex.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                "apps.core.context_processors.navigation",
                "apps.core.context_processors.demo_mode",
                "apps.notifications.context_processors.notification_unread_count",
                "apps.organizations.context_processors.active_organization",
            ],
        },
    },
]

WSGI_APPLICATION = "apex.wsgi.application"
ASGI_APPLICATION = "apex.asgi.application"

# Channels — the realtime layer.
#
# Defaults to the in-memory layer so dev + tests need zero infra.
# Production should set REDIS_URL and install the `realtime` extra
# (see pyproject.toml [project.optional-dependencies]). When REDIS_URL
# is set, prod.py upgrades to the channels_redis backend.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Form renderer — use the project's TEMPLATES configuration so custom
# widgets in apps.core.widgets can resolve their templates from the
# project's templates/ directory (templates/widgets/*.html).
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/leads/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

AUTH_USER_MODEL = "accounts.User"

# Custom CSRF reject page — friendlier than Django's default. Triggered
# when a form's CSRF token doesn't match the cookie (most often: stale
# tab open across the hourly demo reseed at HH:05).
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# ── Content Security Policy (Django 6) ───────────────────────────────────
# CSP blocks XSS by allowlisting where scripts/styles/images can come from.
# Tradeoffs we're accepting:
#   - 'unsafe-eval' on script-src — Alpine.js evaluates directives via
#     `new Function()`, which CSP otherwise blocks. There's an Alpine "CSP
#     build" that avoids this but it doesn't support all our patterns.
#   - 'unsafe-inline' on style-src — ApexCharts injects inline styles for
#     SVG; Alpine x-bind:style sets them too. Style-XSS is much less
#     dangerous than script-XSS (style can't exec code), so this is a fine
#     tradeoff.
#   - data: on img-src — for inline avatars + Tailwind's gradient utilities.
#   - blob: on img-src — for chart-export PNG previews.
# Inline <script> tags must carry `nonce="{{ request.csp_nonce }}"` —
# the csp() context processor exposes the per-request nonce.
from django.utils.csp import CSP  # noqa: E402

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [
        CSP.SELF,
        CSP.NONCE,
        "'unsafe-eval'",                # Alpine.js
        "https://unpkg.com",            # HTMX, Alpine, Leaflet
        "https://cdn.jsdelivr.net",     # ApexCharts, FullCalendar, SortableJS
    ],
    "style-src": [
        CSP.SELF,
        "'unsafe-inline'",              # ApexCharts SVG, Alpine x-bind:style
        "https://unpkg.com",            # Leaflet CSS
        "https://cdn.jsdelivr.net",
    ],
    "img-src": [
        CSP.SELF,
        "data:",                        # inline avatars, Tailwind gradients
        "blob:",                        # chart-export previews
        "https:",                       # external avatar hosts
    ],
    "font-src": [CSP.SELF, "data:"],
    "connect-src": [
        CSP.SELF,
        "wss:",                         # WebSocket consumers (Channels)
        "ws:",                          # dev fallback when not on https
    ],
    "frame-ancestors": [CSP.NONE],      # belt-and-braces vs. clickjacking
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],           # <object>/<embed>/<applet> are dead
    "form-action": [CSP.SELF],
    "manifest-src": [CSP.SELF],         # PWA manifest at /manifest.webmanifest
    "worker-src": [CSP.SELF],           # PWA service worker at /sw.js
}

# ── Demo mode ────────────────────────────────────────────────────────────
# When DEMO_MODE is True, the login page pre-fills the demo credentials
# and shows them in a banner so reviewers can sign in with one click.
# Defaults to False; dev.py turns it on. Production stays off.
DEMO_MODE = False
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "ApexShowcase!2026"

# ── TrackBox lead API ────────────────────────────────────────────────────
# Integration with the external TrackBox CRM (track.fintechgurus.org).
# When unset, the Leads pages render a configuration warning instead of
# calling out. ai/ci/gi are the partner identifiers used on lead push.
TRACKBOX_BASE_URL = os.environ.get("TRACKBOX_BASE_URL", "")
TRACKBOX_USERNAME = os.environ.get("TRACKBOX_USERNAME", "")
TRACKBOX_PASSWORD = os.environ.get("TRACKBOX_PASSWORD", "")
TRACKBOX_API_KEY = os.environ.get("TRACKBOX_API_KEY", "")
TRACKBOX_AI = os.environ.get("TRACKBOX_AI", "")
TRACKBOX_CI = os.environ.get("TRACKBOX_CI", "1")
TRACKBOX_GI = os.environ.get("TRACKBOX_GI", "")

# Shared secret for the public TrackBox postback receiver (/leads/postback/).
# When unset, the endpoint rejects everything.
LEADS_POSTBACK_TOKEN = os.environ.get("LEADS_POSTBACK_TOKEN", "")

# ── Site access gate (HTTP Basic Auth) ───────────────────────────────────
# Quando SITE_GATE_USER e SITE_GATE_PASSWORD sono impostate, l'intero sito
# è protetto da una password del browser TRANNE gli endpoint pubblici qui
# sotto, necessari al flusso lead. Lasciare vuote = gate disattivato.
SITE_GATE_USER = os.environ.get("SITE_GATE_USER", "")
SITE_GATE_PASSWORD = os.environ.get("SITE_GATE_PASSWORD", "")
SITE_GATE_REALM = os.environ.get("SITE_GATE_REALM", "IceTimes")
SITE_GATE_EXEMPT_PREFIXES = (
    "/b/",                 # landing pubbliche dei broker
    "/t/",                 # link corti di tracciamento
    "/api/track/",         # endpoint track visit/click/lead
    "/api/create-lead",    # alias create-lead
    "/leads/postback/",    # postback broker (TrackBox & co.)
    "/__health",           # health check
    "/robots.txt",
    "/sw.js",              # service worker PWA
    "/manifest.webmanifest",
    "/offline/",
    "/static/",            # asset
)

# ── IREV affiliate API ───────────────────────────────────────────────────
# Second lead source (stylishwnt.com). Token is IP-whitelisted on the
# IREV side. Goal UUIDs distinguish plain leads from FTD deposits.
IREV_BASE_URL = os.environ.get("IREV_BASE_URL", "")
IREV_TOKEN = os.environ.get("IREV_TOKEN", "")
IREV_AFFILIATE_ID = os.environ.get("IREV_AFFILIATE_ID", "")
IREV_OFFER_ID = os.environ.get("IREV_OFFER_ID", "")
IREV_GOAL_LEAD = os.environ.get("IREV_GOAL_LEAD", "")
IREV_GOAL_FTD = os.environ.get("IREV_GOAL_FTD", "")

# ── Mediafront (Midas) affiliate API ─────────────────────────────────────────
MEDIAFRONT_BASE_URL = os.environ.get("MEDIAFRONT_BASE_URL", "")
MEDIAFRONT_API_KEY = os.environ.get("MEDIAFRONT_API_KEY", "")
MEDIAFRONT_BOX = os.environ.get("MEDIAFRONT_BOX", "")
MEDIAFRONT_SUB1 = os.environ.get("MEDIAFRONT_SUB1", "funnel")

# ── SPM Monster affiliate API ─────────────────────────────────────────────────
SPMMONSTER_BASE_URL = os.environ.get("SPMMONSTER_BASE_URL", "")
SPMMONSTER_API_KEY = os.environ.get("SPMMONSTER_API_KEY", "")
SPMMONSTER_AFFC = os.environ.get("SPMMONSTER_AFFC", "")
SPMMONSTER_BXC = os.environ.get("SPMMONSTER_BXC", "")
SPMMONSTER_VTC = os.environ.get("SPMMONSTER_VTC", "")

# ── Affinitrax seller API ────────────────────────────────────────────────
# Third lead source (affinitrax.com). X-API-Key header auth, no IP lock.
AFFINITRAX_BASE_URL = os.environ.get("AFFINITRAX_BASE_URL", "")
AFFINITRAX_API_KEY = os.environ.get("AFFINITRAX_API_KEY", "")

