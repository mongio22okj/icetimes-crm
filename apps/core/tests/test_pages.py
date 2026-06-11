"""Tests for the static showcase pages — Coming Soon, Maintenance, 503."""
import pytest

pytestmark = pytest.mark.django_db


def test_coming_soon_renders_for_anon(client):
    r = client.get("/pages/coming-soon/")
    assert r.status_code == 200
    assert b"Coming Soon" in r.content or b"Launching soon" in r.content
    assert b"Notify me" in r.content


def test_coming_soon_includes_launch_target(client):
    r = client.get("/pages/coming-soon/")
    # Countdown gets a Date string injected as x-data arg
    assert b"countdownTimer(" in r.content


def test_coming_soon_subscribe_redirects_back(client):
    r = client.post("/pages/coming-soon/subscribe/", data={"email": "test@example.com"})
    assert r.status_code == 302
    assert r.url.endswith("/pages/coming-soon/")


def test_coming_soon_subscribe_handles_blank_email(client):
    r = client.post("/pages/coming-soon/subscribe/", data={"email": ""})
    assert r.status_code == 302


def test_maintenance_returns_503(client):
    r = client.get("/pages/maintenance/")
    assert r.status_code == 503
    assert b"maintenance" in r.content.lower()
    assert b"right back" in r.content.lower()


def test_maintenance_shows_eta_strip(client):
    r = client.get("/pages/maintenance/")
    assert b"Started" in r.content
    assert b"Expected back" in r.content


def test_service_unavailable_returns_503(client):
    r = client.get("/pages/503/")
    assert r.status_code == 503
    assert b"503" in r.content
    assert b"Service Unavailable" in r.content


def test_service_unavailable_shows_incident_reference(client):
    r = client.get("/pages/503/")
    assert b"INC-" in r.content


# ── Galleries ─────────────────────────────────────────────────────────

def test_forms_gallery_redirects_anon(client):
    r = client.get("/pages/forms/")
    assert r.status_code == 302  # dashboard layout requires auth


def test_forms_gallery_renders_for_auth(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/forms/")
    assert r.status_code == 200
    body = r.content.decode()
    # Phase 12 rewrite: page heading + key category headers must render.
    assert "<h1" in body and "Forms" in body
    for needle in ("Floating label input", "Multi-select", "File dropzone",
                   "Validation states", "Sizes"):
        assert needle in body


def test_widgets_gallery_renders_for_auth(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/widgets/")
    assert r.status_code == 200
    assert b"Widgets gallery" in r.content
    assert b"Stat cards" in r.content
    assert b"Leaderboard" in r.content
    assert b"Activity timeline" in r.content
    assert b"Empty states" in r.content


def test_widgets_gallery_includes_seeded_payloads(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/widgets/")
    # Specific demo data the view passes through
    assert b"Sara Chen" in r.content
    assert b"Q1 revenue" in r.content
    assert len(r.context["stat_cards"]) == 4
    assert len(r.context["leaderboard"]) == 5


# ── Datatable showcase page ───────────────────────────────────────────
# Phase 11 replaced the per-page mock backend with a links-out showcase
# pointing at the real TableView-powered list views (Customers, Orders,
# Invoices, Products, Users, Activity). Those each have their own tests
# under apps/core/tables/tests/. This page just renders link cards.

def test_datatable_showcase_redirects_anon(client):
    r = client.get("/pages/datatable/")
    assert r.status_code == 302


def test_datatable_showcase_renders_links_to_real_tables(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/datatable/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Datatable" in body
    # All six list-view link cards must be present
    for needle in ("Customers", "Orders", "Invoices", "Products",
                   "Users", "Activity log"):
        assert needle in body


# ── API docs ──────────────────────────────────────────────────────────

def test_api_docs_redirects_anon(client):
    r = client.get("/pages/api-docs/")
    assert r.status_code == 302


def test_api_docs_renders_all_sections(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/api-docs/")
    assert r.status_code == 200
    # Section headings + sidebar entries must be present
    for needle in (b"Apex API", b"Authentication", b"Customers", b"Orders",
                   b"Invoices", b"Webhooks", b"Errors", b"Rate limits",
                   b"SDKs", b"Changelog"):
        assert needle in r.content, f"missing section: {needle!r}"


def test_api_docs_renders_method_pills(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/api-docs/")
    # All four pill colors should appear at least once
    assert b">GET<" in r.content
    assert b">POST<" in r.content
    assert b">PATCH<" in r.content
    assert b">DEL<" in r.content


def test_api_docs_includes_endpoint_table(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/api-docs/")
    # The view passes 9 endpoints in the context
    assert len(r.context["endpoints"]) == 9
    assert b"/customers/{id}" in r.content
    assert b"/invoices/{id}/send" in r.content


def test_api_docs_shows_base_url(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/api-docs/")
    assert b"api.apex.example/v1" in r.content


# ── Maps ──────────────────────────────────────────────────────────────

def test_maps_redirects_anon(client):
    r = client.get("/pages/maps/")
    assert r.status_code == 302


def test_maps_renders_for_auth(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/maps/")
    assert r.status_code == 200
    assert b"Maps" in r.content
    # Both map containers + Leaflet script
    assert b'id="customers-map"' in r.content
    assert b'id="density-map"' in r.content
    assert b"leaflet.js" in r.content


def test_maps_embeds_locations_payload(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/maps/")
    assert b'id="locations-data"' in r.content
    locations = r.context["locations"]
    assert len(locations) >= 10  # we ship 15 cities
    assert all({"city", "country", "lat", "lng", "customers", "mrr"}
               <= set(p.keys()) for p in locations)


def test_maps_totals_match_dataset(client):
    from apps.accounts.tests.factories import UserFactory
    client.force_login(UserFactory())
    r = client.get("/pages/maps/")
    locations = r.context["locations"]
    totals = r.context["totals"]
    assert totals["customers"] == sum(p["customers"] for p in locations)
    assert totals["mrr"] == sum(p["mrr"] for p in locations)
    assert totals["cities"] == len(locations)
    assert totals["countries"] == len({p["country"] for p in locations})
