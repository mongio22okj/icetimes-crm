"""End-to-end smoke tests via Playwright. Mirrors Apex Next.js e2e/smoke.spec.ts."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e]


@pytest.fixture(autouse=True)
def _setup_page(page: Page):
    """Set viewport and timeouts for all E2E tests."""
    page.set_viewport_size({"width": 1280, "height": 800})
    page.set_default_timeout(5000)


def _login(page: Page, server_url: str) -> None:
    """Helper: log in as demo user."""
    page.goto(f"{server_url}/accounts/login/")
    page.fill('input[name="username"]', "demo")
    page.fill('input[name="password"]', "ApexShowcase!2026")
    page.click('button[type="submit"]')
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_login_page_loads(page: Page, server_url):
    page.goto(f"{server_url}/accounts/login/")
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()


def test_login_and_see_dashboard(page: Page, server_url):
    _login(page, server_url)


def test_sidebar_navigates_to_products(page: Page, server_url):
    _login(page, server_url)
    page.get_by_role("link", name="Products").first.click()
    expect(page.get_by_role("heading", name="Products")).to_be_visible()


def test_theme_toggle_flips_html_class(page: Page, server_url):
    _login(page, server_url)

    # Wait for Alpine to hydrate before clicking
    page.wait_for_function("window.Alpine !== undefined")

    html = page.locator("html")
    before = html.get_attribute("class") or ""
    page.get_by_role("button", name="Toggle theme").click()
    after = html.get_attribute("class") or ""
    assert after != before, f"Theme didn't toggle; before={before!r} after={after!r}"

    # Toggle back
    page.get_by_role("button", name="Toggle theme").click()
    after_second_toggle = html.get_attribute("class") or ""
    assert after_second_toggle == before, "Theme didn't revert on second toggle"


def test_orders_list_renders(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/orders/")
    expect(page.get_by_role("heading", name="Orders")).to_be_visible()
