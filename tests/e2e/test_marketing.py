"""E2E coverage for Phase 7a marketing landings."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_anonymous_can_view_analytics_landing(page, server_url):
    page.goto(f"{server_url}/landing/analytics/")
    page.locator("text=Decisions backed by data").first.wait_for(state="visible", timeout=5000)
    # Sign in CTA visible (anonymous user)
    page.locator("text=Sign in").first.wait_for(state="visible")


def test_hub_navigates_to_all_variants(page, server_url):
    page.goto(f"{server_url}/landing/")
    # All 4 variant links present
    for label in ["Analytics", "SaaS", "CRM", "eCommerce"]:
        page.locator(f"main >> text={label}").first.wait_for(state="visible", timeout=5000)


def test_authenticated_user_sees_dashboard_cta_on_landing(page, server_url):
    # Login as demo
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "demo")
    page.fill("#id_password", "ApexShowcase!2026")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")

    page.goto(f"{server_url}/landing/saas/")
    page.locator("text=Dashboard").first.wait_for(state="visible", timeout=5000)
