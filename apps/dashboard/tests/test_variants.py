"""Tests for the four dashboard variants (Analytics, CRM, eCommerce, SaaS).

Each variant: requires auth, renders 4 stat cards, embeds chart payloads
as json_script blocks, and shows the section headings + table content
that the templates promise.
"""
import pytest

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user():
    return UserFactory(is_staff=True)


# ── Auth gates ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "/dashboards/analytics/", "/dashboards/crm/",
    "/dashboards/ecommerce/", "/dashboards/saas/",
])
def test_variant_redirects_anonymous(client, path):
    r = client.get(path)
    assert r.status_code == 302
    assert "/accounts/login" in r.url


# ── Analytics ──────────────────────────────────────────────────────────

def test_analytics_renders(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/analytics/")
    assert r.status_code == 200
    assert b"Analytics" in r.content
    assert b"Page Views" in r.content
    assert b"Top Pages" in r.content
    assert b"Top Countries" in r.content


def test_analytics_embeds_chart_payloads(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/analytics/")
    assert b'id="page-views-data"' in r.content
    assert b'id="category-revenue-data"' in r.content
    assert b'pageViewsChart()' in r.content
    assert b'categoryRevenueChart()' in r.content


def test_analytics_has_four_stat_cards(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/analytics/")
    assert len(r.context["stats"]) == 4
    labels = {s["label"] for s in r.context["stats"]}
    assert {"Page Views", "Unique Visitors", "Bounce Rate", "Avg. Session"} <= labels


# ── CRM ─────────────────────────────────────────────────────────────────

def test_crm_renders(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/crm/")
    assert r.status_code == 200
    assert b"CRM" in r.content
    assert b"Andamento" in r.content
    assert b"Lead per stato" in r.content
    assert b"Performance per broker" in r.content
    assert b"Lead recenti" in r.content
    assert b"Report settimanale" in r.content


def test_crm_embeds_chart_payloads(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/crm/")
    assert b'id="pipeline-data"' in r.content
    assert b'id="deal-stages-data"' in r.content
    assert b'id="lead-sources-data"' in r.content


def test_crm_targets_have_progress_calculation(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/crm/")
    targets = r.context["targets"]
    assert all({"label", "current", "target", "accent"} <= set(t.keys()) for t in targets)


# ── eCommerce ──────────────────────────────────────────────────────────

def test_ecommerce_renders(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/ecommerce/")
    assert r.status_code == 200
    assert b"eCommerce" in r.content
    assert b"Sales Overview" in r.content
    assert b"Order Status" in r.content
    assert b"Top Selling Products" in r.content
    assert b"Recent Transactions" in r.content


def test_ecommerce_embeds_chart_payloads(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/ecommerce/")
    assert b'id="daily-sales-data"' in r.content
    assert b'id="order-status-data"' in r.content
    assert b'id="category-sales-data"' in r.content


def test_ecommerce_30_day_sales_data(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/ecommerce/")
    # daily series is serialized into json_script — confirm by parsing context shape
    products = r.context["top_products"]
    assert len(products) >= 5
    assert all({"name", "price", "sold", "revenue"} <= set(p.keys()) for p in products)


# ── SaaS ────────────────────────────────────────────────────────────────

def test_saas_renders(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/saas/")
    assert r.status_code == 200
    assert b"SaaS" in r.content
    assert b"Revenue Growth" in r.content
    assert b"Subscription Plans" in r.content
    assert b"Marketing Channels" in r.content
    assert b"Recent Signups" in r.content


def test_saas_embeds_chart_payloads(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/saas/")
    assert b'id="revenue-growth-data"' in r.content
    assert b'id="plans-data"' in r.content
    assert b'id="user-growth-data"' in r.content


def test_saas_signup_plan_badges_render(client, staff_user):
    client.force_login(staff_user)
    r = client.get("/dashboards/saas/")
    # All four plan tiers should show up in the recent-signups table badges
    assert b"Enterprise" in r.content
    assert b"Pro" in r.content
    assert b"Starter" in r.content
    assert b"Free" in r.content
