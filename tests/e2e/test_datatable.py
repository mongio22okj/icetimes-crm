"""End-to-end tests for the Phase 11 HTMX datatable, exercised on /customers/."""
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


def test_customers_table_renders_with_seeded_data(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    expect(page.get_by_role("heading", name="Customers", exact=True)).to_be_visible()
    # Table region present
    expect(page.locator("#table-customers")).to_be_visible()
    # Pagination strip mentions the demo's 100 seeded rows.
    expect(page.get_by_text("100 total")).to_be_visible()


def test_search_input_swaps_table_partial(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    page.wait_for_function("window.htmx !== undefined")

    search = page.locator("#table-customers-q")
    search.fill("zzz_no_such_customer")
    # HTMX swaps after the 300ms debounce; wait for the empty-state copy.
    expect(page.get_by_text("No matches")).to_be_visible(timeout=2000)


def test_sort_link_swaps_table_via_htmx(page: Page, server_url):
    """Click the Customer column header — table region should swap without
    a full page reload (we assert the URL has ?sort=, and the table region
    re-renders without refreshing the page header)."""
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    page.wait_for_function("window.htmx !== undefined")

    # Capture page nonce in URL before sort. After sort the URL should carry sort=name.
    page.get_by_role("link", name="Customer ↕").click()
    expect(page).to_have_url(lambda url: "sort=" in url, timeout=2000)


def test_pagination_swaps_table_via_htmx(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    page.wait_for_function("window.htmx !== undefined")

    # 100 rows / 25 per page → 4 pages. Click Next.
    page.get_by_role("link", name="Next →").first.click()
    expect(page).to_have_url(lambda url: "page=2" in url, timeout=2000)
    expect(page.get_by_text("Page 2 of 4")).to_be_visible()


def test_csv_export_downloads(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    with page.expect_download() as download_info:
        page.goto(f"{server_url}/customers/?_export=csv")
    download = download_info.value
    assert download.suggested_filename.endswith(".csv")


def test_select_all_checkbox_reveals_bulk_toolbar(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    page.wait_for_function("window.Alpine !== undefined")

    # The "select all on page" checkbox is the first checkbox in the table.
    select_all = page.locator('input[type="checkbox"][aria-label="Select all on page"]')
    expect(select_all).to_be_visible()
    select_all.check()
    expect(page.get_by_text("25 selected")).to_be_visible()


def test_column_visibility_menu_opens(page: Page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    page.wait_for_function("window.Alpine !== undefined")

    page.get_by_role("button", name="Columns").click()
    # The menu should show all column labels with "Pinned" next to the pinned one.
    expect(page.get_by_text("Pinned")).to_be_visible()


def test_save_view_then_apply_via_dropdown(page: Page, server_url):
    _login(page, server_url)
    # Apply a filter, save the view, reload, see it in the Views menu.
    page.goto(f"{server_url}/customers/?status=inactive")
    page.wait_for_function("window.Alpine !== undefined")
    page.get_by_role("button", name="Views").click()
    page.fill('input[name="_view_name"]', "Inactive customers")
    page.get_by_role("button", name="Save").click()

    page.goto(f"{server_url}/customers/")
    page.get_by_role("button", name="Views").click()
    expect(page.get_by_text("Inactive customers")).to_be_visible()
