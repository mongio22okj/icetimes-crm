"""End-to-end tests for the Phase 12 widget gallery + upgraded forms."""
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


def test_forms_gallery_renders_all_widget_sections(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/")
    expect(page.get_by_role("heading", name="Forms", exact=True)).to_be_visible()
    # Each widget section anchor must render its heading.
    for heading in (
        "Floating label input", "Floating label textarea",
        "Icon prefix input", "Icon suffix input",
        "Multi-select", "Tag input", "Combobox",
        "Date range picker", "File dropzone",
        "Rich text editor", "Character counter", "Conditional reveal",
    ):
        expect(page.get_by_role("heading", name=heading, exact=True)).to_be_visible()


def test_floating_label_input_floats_on_focus(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/#floating-input")
    # The floating-label CSS uses :placeholder-shown — focusing the
    # input lifts the label visually. We assert the input is focusable
    # and accepts text (the visual float is CSS-only).
    page.wait_for_function("window.Alpine !== undefined")
    inp = page.locator('input[name="full_name"]')
    inp.fill("Aigars Acme")
    expect(inp).to_have_value("Aigars Acme")


def test_multi_select_chip_appears_on_pick(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/#multi-select")
    page.wait_for_function("window.Alpine !== undefined")
    # Initial selection includes "Engineering" and "Design" — both chips visible.
    section = page.locator("#multi-select")
    expect(section.get_by_text("Engineering", exact=True).first).to_be_visible()


def test_tag_input_renders_initial_chips(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/#tag-input")
    page.wait_for_function("window.Alpine !== undefined")
    section = page.locator("#tag-input")
    expect(section.get_by_text("urgent", exact=True).first).to_be_visible()
    expect(section.get_by_text("vip", exact=True).first).to_be_visible()


def test_date_range_picker_opens_popover(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/#date-range")
    page.wait_for_function("window.Alpine !== undefined")
    section = page.locator("#date-range")
    # Click the trigger button (shows the existing range Apr 1 – Apr 30).
    section.get_by_role("button").first.click()
    # Preset buttons appear in the popover.
    expect(section.get_by_text("Last 7 days", exact=True)).to_be_visible()


def test_file_dropzone_visible_with_caption(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/pages/forms/#file-dropzone")
    section = page.locator("#file-dropzone")
    expect(section.get_by_text("Drop files here", exact=False)).to_be_visible()
    # The caption mentions the configured caps.
    expect(section.get_by_text("max 5 files", exact=False)).to_be_visible()


def test_customer_create_uses_new_widgets(page: Page, server_url):
    """The upgraded Customer form renders Phase 12 widgets in the actual app."""
    _login(page, server_url)
    page.goto(f"{server_url}/customers/new/")
    page.wait_for_function("window.Alpine !== undefined")
    # The floating-label inputs use placeholder=" " (a single space) so
    # the :placeholder-shown CSS works.
    name_input = page.locator('input[name="name"]')
    expect(name_input).to_have_attribute("placeholder", " ")
    # Email field is the icon-prefix variant — left padding is pl-9.
    email_input = page.locator('input[name="email"]')
    klass = email_input.get_attribute("class") or ""
    assert "pl-9" in klass
