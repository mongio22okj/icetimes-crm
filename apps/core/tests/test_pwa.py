"""PWA endpoint tests — manifest + service worker + offline fallback."""
import json

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_manifest_is_valid_json(client):
    r = client.get(reverse("pwa_manifest"))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/manifest+json")
    data = json.loads(r.content)
    # Required fields per W3C Manifest spec — Lighthouse checks all of these.
    assert data["name"]
    assert data["short_name"]
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"
    assert data["theme_color"]
    assert data["background_color"]
    # Must have at least one 192x192 + one 512x512 icon (Lighthouse).
    sizes = {icon["sizes"] for icon in data["icons"] if "sizes" in icon}
    assert "192x192" in sizes
    assert "512x512" in sizes


@pytest.mark.django_db
def test_manifest_icon_urls_are_absolute_paths(client):
    """Icon URLs must be absolute paths so the manifest works regardless
    of where it's served from."""
    r = client.get(reverse("pwa_manifest"))
    data = json.loads(r.content)
    for icon in data["icons"]:
        assert icon["src"].startswith("/"), f"icon {icon} has non-absolute src"


@pytest.mark.django_db
def test_manifest_includes_maskable_icon(client):
    """A maskable icon is what makes Android home-screen icons look
    polished (not the generic letter-in-circle fallback)."""
    r = client.get(reverse("pwa_manifest"))
    data = json.loads(r.content)
    purposes = {icon.get("purpose", "any") for icon in data["icons"]}
    assert "maskable" in purposes


@pytest.mark.django_db
def test_service_worker_serves_javascript(client):
    r = client.get(reverse("pwa_sw"))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/javascript")
    body = r.content.decode()
    # Required handlers
    assert "addEventListener" in body
    assert '"install"' in body
    assert '"activate"' in body
    assert '"fetch"' in body
    # Push handlers (Phase 13 integration)
    assert '"push"' in body
    assert '"notificationclick"' in body


@pytest.mark.django_db
def test_service_worker_is_no_cache(client):
    """If the SW itself is cached by the browser, deploys never propagate."""
    r = client.get(reverse("pwa_sw"))
    cc = r.headers.get("Cache-Control", "")
    assert "no-cache" in cc or "no-store" in cc or "max-age=0" in cc


@pytest.mark.django_db
def test_service_worker_includes_cache_version(client):
    """Cache version string changes per deploy so SW cache invalidates."""
    r = client.get(reverse("pwa_sw"))
    body = r.content.decode()
    # Should reference the cache_version constant
    import re
    assert re.search(r'apex-shell-[a-f0-9]{8}', body) is not None


@pytest.mark.django_db
def test_offline_fallback_page_renders(client):
    r = client.get(reverse("pwa_offline"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "offline" in body.lower()
    assert "Try again" in body


@pytest.mark.django_db
def test_base_html_links_manifest_and_icons(client, db):
    """The dashboard layout must wire <link rel="manifest"> + <link rel="icon">."""
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    user = get_user_model().objects.create_user(
        username="pwa", email="p@x.io", password="pw",
        is_staff=True, email_verified_at=timezone.now(),
    )
    client.force_login(user)
    r = client.get("/")
    body = r.content.decode()
    assert 'rel="manifest"' in body
    assert "/manifest.webmanifest" in body
    assert 'rel="icon"' in body
    # PWA install bootstrap script
    assert "/static/js/pwa." in body or "/static/js/pwa.js" in body
    # theme-color for the address bar tint on installed PWAs
    assert 'name="theme-color"' in body
