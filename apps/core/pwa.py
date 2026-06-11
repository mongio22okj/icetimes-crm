"""Progressive Web App endpoints — manifest + service worker.

`/manifest.webmanifest` is served by a Django view rather than as a
static file so we can:

  - reference icons via {% static %} so WhiteNoise's manifest hashing
    cache-busts updates on every deploy
  - read brand metadata from settings without duplicating it in JSON
  - keep the manifest in source-control as Python (easier to lint/grep
    than a static .json that contains URLs)

`/sw.js` is similarly view-served so the cache-version string can be
tied to deploy-time data (we use the SECRET_KEY hash as a fingerprint
that changes on every deploy).
"""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
def manifest(request):
    """W3C-compliant Web App Manifest — drives the install prompt."""
    return JsonResponse({
        "name": "Apex Dashboard",
        "short_name": "Apex",
        "description": "Production-ready Django admin dashboard.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "theme_color": "#585cde",
        "background_color": "#0a0a0a",
        "lang": "en",
        "dir": "ltr",
        "categories": ["productivity", "business"],
        "icons": [
            {
                "src": static("icons/icon.svg"),
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any",
            },
            {
                "src": static("icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("icons/icon-maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "Dashboard",
                "url": "/",
                "icons": [{
                    "src": static("icons/icon-192.png"),
                    "sizes": "192x192",
                }],
            },
            {
                "name": "Notifications",
                "url": "/notifications/",
            },
        ],
    }, content_type="application/manifest+json")


def _cache_version() -> str:
    """A stable-per-deploy fingerprint for service worker cache busting.

    Hash of SECRET_KEY (which changes per deploy in real prod via env)
    so the SW invalidates its cache when the app is redeployed. In dev
    the key is static, which is fine — manual SW unregister works.
    """
    return hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:8]


@never_cache
@require_GET
def service_worker(request):
    """Serve sw.js from the site root.

    SW scope is constrained by its URL path: a worker at `/static/sw.js`
    can only control `/static/*` requests, so we expose it at `/sw.js`
    instead so it can claim the entire origin.
    """
    return render(request, "pwa/sw.js", {
        "cache_version": _cache_version(),
        "shell_url": "/",
        "offline_url": "/offline/",
        # Pre-cached static assets — the absolute minimum for the offline shell.
        "precache_assets": [
            static("css/app.css"),
            static("js/shell.js"),
            static("js/app.js"),
            static("icons/icon-192.png"),
        ],
    }, content_type="application/javascript; charset=utf-8")


@require_GET
def offline(request):
    """Standalone page the SW falls back to when network is unavailable.

    Kept as its own view so the SW can pre-cache one specific URL rather
    than trying to cache + serve every page.
    """
    return render(request, "pwa/offline.html")
