"""E2E coverage for Phase 8 UX surfaces (wizard, charts, lock)."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_wizard_happy_path(page, server_url):
    from apps.wizard.models import WizardSubmission
    _login(page, server_url)
    page.goto(f"{server_url}/wizard/")

    # Step 1
    page.locator("input[name='name']").wait_for(state="visible")
    page.fill("input[name='name']", "Wizard Tester")
    page.fill("input[name='email']", "wiz@example.com")
    page.click("button:has-text('Continue')")

    # Step 2
    page.locator("select[name='team_size']").wait_for(state="visible")
    page.select_option("select[name='team_size']", value="2-10")
    page.click("button:has-text('Continue')")

    # Step 3
    page.locator("select[name='theme']").wait_for(state="visible")
    page.select_option("select[name='theme']", value="dark")
    page.click("button:has-text('Continue')")

    # Review → submit
    page.locator("text=Review and submit").wait_for(state="visible")
    page.click("button:has-text('Submit onboarding')")

    # Done page
    page.locator("text=You're all set").first.wait_for(state="visible", timeout=5000)
    assert WizardSubmission.objects.filter(name="Wizard Tester").exists()


def test_charts_showcase_renders_8_charts(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/charts/")
    # Wait for ApexCharts to mount one of the chart svg containers
    page.locator("#cs-bar svg").first.wait_for(state="visible", timeout=10000)
    # Ensure all 8 chart wrapper divs exist
    for cid in ["cs-bar", "cs-line", "cs-area", "cs-donut", "cs-radial", "cs-heatmap", "cs-scatter", "cs-mixed"]:
        assert page.locator(f"#{cid}").count() == 1


def test_lock_unlock_flow(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/lock/")
    # Lock screen visible
    page.locator("text=session is locked").wait_for(state="visible", timeout=5000)
    # Trying to navigate to dashboard should redirect back to /lock/
    page.goto(f"{server_url}/")
    page.wait_for_url(f"{server_url}/lock/")

    # Enter correct password to unlock
    page.fill("input[name='password']", "ApexShowcase!2026")
    page.click("button:has-text('Unlock')")
    page.wait_for_url(f"{server_url}/")
