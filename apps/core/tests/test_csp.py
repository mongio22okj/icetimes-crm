"""Test that the Django 6 ContentSecurityPolicyMiddleware is wired correctly."""
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_csp_header_present_on_all_responses(client):
    r = client.get(reverse("login"))
    assert r.status_code == 200
    assert "Content-Security-Policy" in r.headers


@pytest.mark.django_db
def test_csp_header_includes_expected_directives(client):
    r = client.get(reverse("login"))
    csp = r.headers["Content-Security-Policy"]
    # Required: lock down everything else to self by default
    assert "default-src 'self'" in csp
    # Required: nonce slot for inline scripts (the per-request value
    # is randomized so we just check the directive exists)
    assert "script-src" in csp and "'nonce-" in csp
    # Required: WebSocket origins allowed (Channels won't work without)
    assert "wss:" in csp
    # Required: clickjacking belt-and-braces
    assert "frame-ancestors 'none'" in csp
    # Required: deprecated <object>/<embed> blocked
    assert "object-src 'none'" in csp


@pytest.mark.django_db
def test_csp_nonce_appears_in_rendered_page(client):
    """The base.html theme-bootstrap script needs a nonce — verify the
    template tag actually rendered the value (not the literal string)."""
    r = client.get(reverse("login"))
    body = r.content.decode()
    # The nonce should appear at least twice: once in the CSP header,
    # once on the inline <script> tag.
    csp = r.headers["Content-Security-Policy"]
    # Pull the nonce value out of the header
    import re
    match = re.search(r"'nonce-([^']+)'", csp)
    assert match is not None, "no nonce in CSP header"
    nonce = match.group(1)
    # That same nonce must be on the inline <script>
    assert f'nonce="{nonce}"' in body, "inline script missing matching nonce"


@pytest.mark.django_db
def test_csp_allows_known_cdns(client):
    """unpkg.com + cdn.jsdelivr.net must be allowed — we load HTMX,
    Alpine, ApexCharts, Leaflet, FullCalendar, SortableJS from them."""
    r = client.get(reverse("login"))
    csp = r.headers["Content-Security-Policy"]
    assert "https://unpkg.com" in csp
    assert "https://cdn.jsdelivr.net" in csp
