"""E2E coverage for Phase 4c Notifications."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_bell_badge_shows_unread_count_on_page_load(page, server_url):
    _login(page, server_url)
    # The seeded demo user has unread notifications; bell badge should be visible
    badge = page.locator("#notification-bell-content button[aria-label='Notifications'] span")
    assert badge.count() > 0
    badge_text = badge.first.text_content()
    assert badge_text and badge_text.strip() != "0"


def test_clicking_bell_opens_dropdown_with_recent_notifications(page, server_url):
    _login(page, server_url)
    # Click the bell button
    page.locator("button[aria-label='Notifications']").click()
    # Dropdown header visible
    page.locator("text=Mark all read").wait_for(state="visible", timeout=2000)
    # Recent notifications should be present (at least one row visible)
    page.locator("#notification-bell-content >> text=/sent|placed|paid|voided/i").first.wait_for(
        state="visible", timeout=2000
    )


def test_mark_all_read_clears_badge(page, server_url):
    _login(page, server_url)
    page.locator("button[aria-label='Notifications']").click()
    page.locator("button:has-text('Mark all read')").first.click()
    # Wait for the HTMX swap; badge should disappear (or read 0)
    page.wait_for_timeout(500)
    badge = page.locator("#notification-bell-content button[aria-label='Notifications'] span")
    # After mark-all-read, the unread badge should not be present
    assert badge.count() == 0


def test_notifications_list_page(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/notifications/")
    # Heading and at least one row visible
    page.locator("h1:has-text('Notifications')").wait_for(state="visible")
    rows = page.locator("section .divide-y > div")
    assert rows.count() > 0
