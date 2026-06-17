"""
Development settings — SQLite + DEBUG=True.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

SECRET_KEY = "django-insecure-dev-only-do-not-use-in-production"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# Use plain static storage in dev — no collectstatic manifest required
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Print outbound email to the terminal in dev; verify links and password-reset
# links become visible in the runserver log.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "Apex Dashboard <noreply@apex.local>"

# Pre-fill the login form with demo credentials in dev. Production (prod.py)
# inherits DEMO_MODE = False from base.py.
DEMO_MODE = True

# Auto-login locale: entra nel sito senza password. SOLO in dev — prod.py
# non imposta questo flag e non carica il middleware sottostante.
DEV_AUTOLOGIN = True
MIDDLEWARE = MIDDLEWARE + [  # noqa: F405
    "apps.core.dev_autologin.DevAutoLoginMiddleware",
]
