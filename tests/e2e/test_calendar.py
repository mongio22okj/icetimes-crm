"""E2E coverage for Phase 6a Calendar."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_calendar_renders_fullcalendar_grid(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/calendar/")
    # FullCalendar adds a `.fc` element when initialized
    page.locator(".fc").wait_for(state="visible", timeout=10000)
    # Toolbar buttons present
    page.locator("button.fc-prev-button").wait_for(state="visible")
    page.locator("button.fc-today-button").wait_for(state="visible")


def test_calendar_shows_seeded_events(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/calendar/")
    # Wait for FullCalendar to fetch + render events
    page.locator(".fc-event").first.wait_for(state="visible", timeout=10000)
    assert page.locator(".fc-event").count() > 0


def test_create_event_flow(page, server_url):
    from datetime import timedelta

    from django.utils import timezone

    _login(page, server_url)
    page.goto(f"{server_url}/calendar/events/new/")
    now = timezone.now() + timedelta(days=1)
    page.fill("input[name='title']", "E2E test event")
    page.fill("input[name='start']", now.strftime("%Y-%m-%dT%H:%M"))
    page.fill("input[name='end']", (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"))
    page.click("button:has-text('Create event')")

    # Lands on calendar
    page.wait_for_url(f"{server_url}/calendar/")
    # Event visible after FullCalendar loads
    page.locator("text=E2E test event").first.wait_for(state="visible", timeout=10000)
