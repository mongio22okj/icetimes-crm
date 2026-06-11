import pyotp
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def _wait_for_alpine(page):
    """Block until apexShell has hydrated, matching the pattern in test_shell.py."""
    page.wait_for_function(
        "() => { const el = document.querySelector('[x-data=\"apexShell()\"]');"
        " return el && el._x_dataStack && el._x_dataStack.length > 0; }",
        timeout=5000,
    )


def test_settings_tabs_navigate_and_highlight_active(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/settings/")
    # Redirects to /settings/profile/
    page.wait_for_url(f"{server_url}/settings/profile/")
    # All 4 tabs render in left-rail
    assert page.locator('nav[aria-label="Settings"] a:has-text("Profile")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Password")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Appearance")').count() == 1
    assert page.locator('nav[aria-label="Settings"] a:has-text("Two-factor")').count() == 1
    # Navigate to Password tab
    page.click('nav[aria-label="Settings"] a:has-text("Password")')
    page.wait_for_url(f"{server_url}/settings/password/")


def test_enable_2fa_end_to_end(page, server_url, django_user_model):
    from django.utils import timezone
    user = django_user_model.objects.create_user(
        username="alice", password="alicepass1", is_staff=False,
    )
    user.email_verified_at = timezone.now()
    user.save()
    _login(page, server_url, username="alice", password="alicepass1")
    page.goto(f"{server_url}/settings/two-factor/")
    # Confirm password in the Enable form and submit
    page.fill('form[action$="/enable/"] input[name="password"]', "alicepass1")
    page.click('form[action$="/enable/"] button[type="submit"]')
    page.wait_for_url(f"{server_url}/settings/two-factor/setup/")
    # Pull secret via ORM so we can compute a valid TOTP in-test
    from apps.accounts.two_factor import TwoFactorDevice
    d = TwoFactorDevice.objects.get(user=user, confirmed=False)
    code = pyotp.TOTP(d.secret).now()
    page.fill('input[name="code"]', code)
    page.click('button:has-text("Verify and enable")')
    page.wait_for_url(f"{server_url}/settings/two-factor/")
    # Recovery codes panel renders with 8 codes
    panel = page.locator("section[aria-live='polite']")
    assert panel.is_visible()
    assert panel.locator("li").count() == 8


def test_login_with_2fa_requires_challenge(page, server_url, django_user_model):
    from django.utils import timezone

    from apps.accounts.two_factor import TwoFactorDevice
    user = django_user_model.objects.create_user(
        username="bob", password="bobpass1", is_staff=False,
    )
    user.email_verified_at = timezone.now()
    user.save()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()

    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "bob")
    page.fill("#id_password", "bobpass1")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/accounts/two-factor/")
    code = pyotp.TOTP(d.secret).now()
    page.fill('input[name="code"]', code)
    page.click('button:has-text("Verify")')
    page.wait_for_url(f"{server_url}/")


def test_appearance_picker_toggles_dark(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/settings/appearance/")
    _wait_for_alpine(page)
    page.click('button:has-text("Dark")')
    # HTML element gets the dark class
    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert is_dark
    stored = page.evaluate("() => localStorage.getItem('theme')")
    assert stored == "dark"
