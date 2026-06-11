import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_unverified_user_redirected_from_dashboard(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")


def test_unverified_user_redirected_from_orders(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/orders/")
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")


def test_unverified_user_can_access_verify_prompt(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 200


def test_unverified_user_can_logout(client):
    user = UserFactory()
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.post("/accounts/logout/")
    assert response.status_code == 302
    # Logout target is /accounts/login/ or / depending on settings.LOGOUT_REDIRECT_URL
    assert "/email/verify/" not in (response["Location"] or "")


def test_verified_user_reaches_dashboard(client):
    user = UserFactory()
    user.email_verified_at = timezone.now()
    user.save()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
