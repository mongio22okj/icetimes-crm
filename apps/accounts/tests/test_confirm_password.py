from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _verified_user(password="testpass-x9!"):
    user = UserFactory()
    user.email_verified_at = timezone.now()
    user.set_password(password)
    user.save()
    return user


def test_confirm_password_renders_form(client):
    user = _verified_user()
    client.force_login(user)
    response = client.get("/password/confirm/")
    assert response.status_code == 200
    assert b"Confirm password" in response.content


def test_confirm_password_correct_sets_session_and_redirects(client):
    user = _verified_user(password="mypass-9")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "mypass-9",
        "next": "/orders/",
    })
    assert response.status_code == 302
    assert response["Location"] == "/orders/"
    assert "password_confirmed_at" in client.session


def test_confirm_password_wrong_stays_on_form(client):
    user = _verified_user(password="good")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "WRONG",
        "next": "/",
    })
    assert response.status_code == 200
    assert "password_confirmed_at" not in client.session


def test_confirm_password_rejects_external_next(client):
    user = _verified_user(password="good")
    client.force_login(user)
    response = client.post("/password/confirm/", {
        "password": "good",
        "next": "https://evil.example.com/",
    })
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_grace_expires_after_3_hours():
    from apps.accounts.mixins import PasswordConfirmationRequiredMixin
    mixin = PasswordConfirmationRequiredMixin()
    class FakeRequest:
        session = {"password_confirmed_at": (timezone.now() - timedelta(hours=4)).isoformat()}
    assert not mixin._is_confirmed(FakeRequest())


def test_fresh_grace_recognized():
    from apps.accounts.mixins import PasswordConfirmationRequiredMixin
    mixin = PasswordConfirmationRequiredMixin()
    class FakeRequest:
        session = {"password_confirmed_at": timezone.now().isoformat()}
    assert mixin._is_confirmed(FakeRequest())
