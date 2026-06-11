"""E2E coverage for Phase 9 i18n."""
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_language_picker_switches_sidebar_to_spanish(page, server_url):
    _login(page, server_url)
    # Sidebar shows English "Dashboard"
    page.locator("aside >> text=Dashboard").first.wait_for(state="visible", timeout=5000)

    # Open user menu, switch language
    page.click("button[aria-label*='User menu']")
    page.locator("select[name='language']").wait_for(state="visible", timeout=5000)
    page.select_option("select[name='language']", value="es")

    # After redirect, sidebar should now read "Tablero"
    page.wait_for_url(f"{server_url}/")
    page.locator("aside >> text=Tablero").first.wait_for(state="visible", timeout=5000)


def test_login_page_renders_in_spanish_via_cookie(page, server_url):
    # Set the language cookie before navigating
    page.context.add_cookies([{
        "name": "django_language",
        "value": "es",
        "url": server_url,
    }])
    page.goto(f"{server_url}/accounts/login/")
    page.locator("text=Iniciar sesión").first.wait_for(state="visible", timeout=5000)
