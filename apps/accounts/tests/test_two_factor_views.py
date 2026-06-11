import pyotp
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def _login_user(client, password="testpw-x9!"):
    user = UserFactory()
    user.set_password(password)
    user.save()
    client.login(username=user.username, password=password)
    return user


def _confirm_password_session(client):
    """Inject a fresh confirm-password grace into the session."""
    from django.utils import timezone
    session = client.session
    session["password_confirmed_at"] = timezone.now().isoformat()
    session.save()


def test_two_factor_view_shows_off_state_for_new_user(client):
    _login_user(client)
    response = client.get("/settings/two-factor/")
    assert response.status_code == 200
    assert b"Enable 2FA" in response.content


def test_enable_requires_correct_password(client):
    user = _login_user(client)
    response = client.post("/settings/two-factor/enable/", {"password": "WRONG"})
    assert response.status_code == 302
    assert not TwoFactorDevice.objects.filter(user=user).exists()


def test_enable_creates_unconfirmed_device_and_redirects_to_setup(client):
    user = _login_user(client, password="good-pass-1")
    response = client.post("/settings/two-factor/enable/", {"password": "good-pass-1"})
    assert response.status_code == 302
    assert response["Location"].endswith("/settings/two-factor/setup/")
    d = TwoFactorDevice.objects.get(user=user)
    assert d.confirmed is False


def test_setup_get_shows_qr_when_unconfirmed_exists(client):
    user = _login_user(client)
    TwoFactorDevice.create_unconfirmed(user)
    response = client.get("/settings/two-factor/setup/")
    assert response.status_code == 200
    assert b"<svg" in response.content
    assert b"Verification code" in response.content


def test_setup_get_redirects_when_no_unconfirmed_device(client):
    _login_user(client)
    response = client.get("/settings/two-factor/setup/")
    assert response.status_code == 302


def test_setup_post_with_valid_code_confirms_and_generates_codes(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/settings/two-factor/setup/", {"code": code}, follow=True)
    d.refresh_from_db()
    assert d.confirmed is True
    assert len(d.recovery_codes) == 8


def test_setup_post_with_invalid_code_renders_error(client):
    user = _login_user(client)
    TwoFactorDevice.create_unconfirmed(user)
    response = client.post("/settings/two-factor/setup/", {"code": "000000"})
    assert response.status_code == 200
    assert b"Invalid code" in response.content
    d = TwoFactorDevice.objects.get(user=user)
    assert d.confirmed is False


def test_disable_without_confirm_grace_redirects(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    response = client.post("/settings/two-factor/disable/")
    assert response.status_code == 302
    assert "/password/confirm/" in response["Location"]
    assert TwoFactorDevice.objects.filter(user=user).exists()


def test_disable_with_confirm_grace_deletes_device(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    _confirm_password_session(client)
    response = client.post("/settings/two-factor/disable/")
    assert response.status_code == 302
    assert not TwoFactorDevice.objects.filter(user=user).exists()


def test_enable_ignored_when_already_confirmed(client):
    user = _login_user(client, password="mypass-9")
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    existing_pk = d.pk

    response = client.post("/settings/two-factor/enable/", {"password": "mypass-9"})
    assert response.status_code == 302
    assert response["Location"].endswith("/settings/two-factor/")
    # Confirmed device is still there, same pk (not replaced)
    d.refresh_from_db()
    assert d.pk == existing_pk
    assert d.confirmed is True


def test_setup_success_flashes_recovery_codes_to_next_page(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/settings/two-factor/setup/", {"code": code}, follow=True)
    # After redirect, the rendered page includes the recovery codes panel
    assert response.status_code == 200
    assert b"Recovery codes" in response.content
    # 8 codes as <li> entries; each contains the "XXXXX-XXXXX" format
    import re
    codes_found = re.findall(br"[A-Z2-9]{5}-[A-Z2-9]{5}", response.content)
    assert len(codes_found) >= 8


def test_regenerate_without_confirm_grace_redirects(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    original_codes = d.generate_recovery_codes()
    response = client.post("/settings/two-factor/regenerate/")
    assert response.status_code == 302
    assert "/password/confirm/" in response["Location"]
    d.refresh_from_db()
    original_hashes = {e["hash"] for e in d.recovery_codes}
    import hashlib
    assert original_hashes == {
        hashlib.sha256(c.upper().encode()).hexdigest() for c in original_codes
    }


def test_regenerate_with_confirm_grace_replaces_codes(client):
    user = _login_user(client)
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    original_codes = d.generate_recovery_codes()
    _confirm_password_session(client)
    response = client.post("/settings/two-factor/regenerate/")
    d.refresh_from_db()
    new_hashes = {e["hash"] for e in d.recovery_codes}
    import hashlib
    original_hashes = {
        hashlib.sha256(c.upper().encode()).hexdigest() for c in original_codes
    }
    assert new_hashes != original_hashes
    assert len(d.recovery_codes) == 8


def test_two_factor_views_require_login(client):
    # All five 2FA endpoints should 302 unauthenticated users to login.
    for path in (
        "/settings/two-factor/",
        "/settings/two-factor/setup/",
    ):
        response = client.get(path)
        assert response.status_code == 302, f"GET {path} should redirect unauth"
        assert "/accounts/login/" in response["Location"]
    for path in (
        "/settings/two-factor/enable/",
        "/settings/two-factor/disable/",
        "/settings/two-factor/regenerate/",
    ):
        response = client.post(path, {})
        assert response.status_code == 302, f"POST {path} should redirect unauth"
        assert "/accounts/login/" in response["Location"]
