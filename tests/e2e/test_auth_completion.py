import pyotp
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_register_and_verify_end_to_end(page, server_url, django_user_model):
    page.goto(f"{server_url}/accounts/register/")
    page.fill("#id_username", "newbie")
    page.fill("#id_email", "newbie@example.com")
    page.fill("#id_first_name", "New")
    page.fill("#id_last_name", "Bie")
    page.fill("#id_password1", "testpass-x9!")
    page.fill("#id_password2", "testpass-x9!")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/email/verify/")
    assert page.locator("text=Check your email").is_visible()

    # Token isn't visible in the UI — compute from the DB and visit the confirm URL directly
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    user = django_user_model.objects.get(username="newbie")
    assert user.email_verified_at is None
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    page.goto(f"{server_url}/email/verify/{uidb64}/{token}/")
    page.wait_for_url(f"{server_url}/")
    user.refresh_from_db()
    assert user.email_verified_at is not None


def test_unverified_user_gated_from_orders(page, server_url, django_user_model):
    user = django_user_model.objects.create_user(
        username="alicee", email="alicee@example.com", password="pw-x9!", is_staff=False,
    )
    user.email_verified_at = None
    user.save()

    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "alicee")
    page.fill("#id_password", "pw-x9!")
    page.click("button[type=submit]")
    # LOGIN_REDIRECT_URL is "/", which hits DashboardView — gated, bounces to /email/verify/
    page.wait_for_url(f"{server_url}/email/verify/")
    # Direct attempt at /orders/ also redirects
    page.goto(f"{server_url}/orders/")
    page.wait_for_url(f"{server_url}/email/verify/")


def test_confirm_password_gate_on_2fa_disable(page, server_url, django_user_model):
    from django.utils import timezone

    from apps.accounts.two_factor import TwoFactorDevice

    user = django_user_model.objects.create_user(
        username="bob", email="bob@example.com", password="pw-x9!", is_staff=False,
    )
    user.email_verified_at = timezone.now()
    user.save()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()

    # Log in (2FA challenge kicks in since 2FA is confirmed)
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", "bob")
    page.fill("#id_password", "pw-x9!")
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/accounts/two-factor/")
    page.fill('input[name="code"]', pyotp.TOTP(d.secret).now())
    page.click('button:has-text("Verify")')
    page.wait_for_url(f"{server_url}/")

    # Click Disable → detours to /password/confirm/ (next=referer = 2FA page)
    page.goto(f"{server_url}/settings/two-factor/")
    page.click('button:has-text("Disable 2FA")')
    page.wait_for_url(lambda url: "/password/confirm/" in url)
    page.fill('input[name="password"]', "pw-x9!")
    page.click('button:has-text("Confirm password")')
    # Confirm redirects back to /settings/two-factor/ with grace now set
    page.wait_for_url(f"{server_url}/settings/two-factor/")
    # User clicks Disable again — this time passes PCRM and deletes device
    page.click('button:has-text("Disable 2FA")')
    page.wait_for_url(f"{server_url}/settings/two-factor/")
    assert not TwoFactorDevice.objects.filter(user=user).exists()
