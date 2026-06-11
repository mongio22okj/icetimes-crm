"""E2E coverage for Phase 6b Kanban."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_board_renders_four_columns(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/kanban/")
    page.locator("[data-kanban-column]").first.wait_for(state="visible", timeout=5000)
    assert page.locator("[data-kanban-column]").count() == 4


def test_seeded_cards_visible(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/kanban/")
    page.locator("article[data-card-id]").first.wait_for(state="visible", timeout=5000)
    assert page.locator("article[data-card-id]").count() > 0


def test_create_card_flow(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/kanban/cards/new/")
    page.fill("input[name='title']", "E2E created card")
    page.select_option("select[name='status']", value="todo")
    page.click("button:has-text('Create card')")

    page.wait_for_url(f"{server_url}/kanban/")
    page.locator("text=E2E created card").first.wait_for(state="visible", timeout=5000)
