import pyotp
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.accounts.two_factor import TwoFactorDevice

pytestmark = pytest.mark.django_db


def _user_with_2fa(password="pw-x9!"):
    user = UserFactory()
    user.set_password(password)
    user.save()
    d = TwoFactorDevice.create_unconfirmed(user)
    d.confirmed = True
    d.save()
    d.generate_recovery_codes()
    return user, d


def test_login_without_2fa_logs_in_directly(client):
    user = UserFactory()
    user.set_password("pw-x9!")
    user.save()
    response = client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    assert response.status_code == 302
    assert "two-factor" not in response["Location"]


def test_login_with_2fa_redirects_to_challenge(client):
    user, _ = _user_with_2fa(password="pw-x9!")
    response = client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/two-factor/")
    assert "_auth_user_id" not in client.session


def test_challenge_get_redirects_to_login_without_session_key(client):
    response = client.get("/accounts/two-factor/")
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/login/")


def test_challenge_post_valid_totp_completes_login(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/accounts/two-factor/", {"code": code})
    assert response.status_code == 302
    assert response["Location"] != reverse("login")
    assert client.session["_auth_user_id"] == str(user.pk)


def test_challenge_post_valid_recovery_code_completes_login(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    codes = d.generate_recovery_codes()
    response = client.post("/accounts/two-factor/", {"code": codes[0]})
    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)
    d.refresh_from_db()
    used = [e for e in d.recovery_codes if e["used_at"] is not None]
    assert len(used) == 1


def test_challenge_post_wrong_code_renders_error(client):
    user, _ = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    response = client.post("/accounts/two-factor/", {"code": "000000"})
    assert response.status_code == 200
    assert b"Invalid code" in response.content
    assert "_auth_user_id" not in client.session


def test_challenge_enforces_attempt_cap(client):
    user, _ = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    # Five wrong attempts
    for _ in range(5):
        client.post("/accounts/two-factor/", {"code": "000000"})
    # Sixth: abandoned, redirected to login
    response = client.post("/accounts/two-factor/", {"code": "000000"})
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/login/")
    assert "pre_2fa_user_id" not in client.session


def test_challenge_preserves_next_url(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/?next=/products/",
                {"username": user.username, "password": "pw-x9!"})
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/accounts/two-factor/", {"code": code})
    assert response.status_code == 302
    assert response["Location"] == "/products/"


def test_challenge_rejects_inactive_user(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    # Deactivate user between the two steps
    user.is_active = False
    user.save()
    code = pyotp.TOTP(d.secret).now()
    response = client.post("/accounts/two-factor/", {"code": code})
    assert response.status_code == 302
    assert response["Location"].endswith("/accounts/login/")
    assert "_auth_user_id" not in client.session


def test_challenge_recovery_code_single_use(client):
    user, d = _user_with_2fa(password="pw-x9!")
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    codes = d.generate_recovery_codes()
    # First use succeeds (completes login)
    client.post("/accounts/two-factor/", {"code": codes[0]})
    assert client.session["_auth_user_id"] == str(user.pk)
    # Log out, log in again, try same code — should fail
    client.logout()
    client.post("/accounts/login/", {"username": user.username, "password": "pw-x9!"})
    response = client.post("/accounts/two-factor/", {"code": codes[0]})
    assert response.status_code == 200
    assert b"Invalid code" in response.content
    assert "_auth_user_id" not in client.session
