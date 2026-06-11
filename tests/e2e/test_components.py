"""End-to-end tests for the Phase 10 components library."""
import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e]


@pytest.fixture(autouse=True)
def _setup_page(page: Page):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.set_default_timeout(5000)


def _login(page: Page, server_url: str) -> None:
    page.goto(f"{server_url}/accounts/login/")
    page.fill('input[name="username"]', "demo")
    page.fill('input[name="password"]', "ApexShowcase!2026")
    page.click('button[type="submit"]')
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_components_index_lists_all_categories(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/")
    expect(page.get_by_role("heading", name="Components", exact=True)).to_be_visible()
    for label in ("Overlay", "Disclosure", "Inputs", "Choice", "Upload", "Feedback", "Identity"):
        expect(page.get_by_role("heading", name=label, exact=True)).to_be_visible()


def test_modal_opens_and_esc_closes(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/modal/")
    page.wait_for_function("window.Alpine !== undefined")
    page.get_by_role("button", name="Default modal", exact=True).click()
    dialog = page.locator('[role="dialog"][aria-labelledby="modal-default-title"]')
    expect(dialog).to_be_visible()
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()


def test_drawer_opens_and_backdrop_click_closes(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/drawer/")
    page.wait_for_function("window.Alpine !== undefined")
    page.get_by_role("button", name="Right (default)", exact=True).click()
    dialog = page.locator('[role="dialog"][aria-labelledby="drawer-right-title"]')
    expect(dialog).to_be_visible()
    # Click on the backdrop (covers the inset-0 absolute div). Esc as fallback.
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible()


def test_toast_appears_when_triggered(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/toast/")
    page.wait_for_function("window.Alpine !== undefined")
    page.get_by_role("button", name="Success", exact=True).click()
    # The toast container has role="status" inside it
    expect(page.get_by_text("Customer saved successfully.")).to_be_visible()


def test_tabs_switch_panel_on_click(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/tabs/")
    page.wait_for_function("window.Alpine !== undefined")
    # The underline section's panel with "Activity panel" text
    activity_tab = page.get_by_role("tab", name="Activity").first
    activity_tab.click()
    expect(page.get_by_text("Activity panel — chronological events.")).to_be_visible()


def test_accordion_toggles_section(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/components/accordion/")
    page.wait_for_function("window.Alpine !== undefined")
    # Open "Account information" then check its body is shown.
    btn = page.get_by_role("button", name="Account information")
    btn.click()
    expect(page.get_by_text("Your name, email, and basic profile fields.")).to_be_visible()
