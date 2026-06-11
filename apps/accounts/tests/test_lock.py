import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_lock_get_sets_session_locked(client):
    user = UserFactory()
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    r = client.get(reverse("lock"))
    assert r.status_code == 200
    assert client.session.get("locked") is True


def test_lock_get_redirects_anonymous_to_login(client):
    r = client.get(reverse("lock"))
    assert r.status_code == 302
    assert "login" in r.url


def test_lock_post_correct_password_unlocks(client):
    user = UserFactory()
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    client.get(reverse("lock"))  # set locked=True
    assert client.session.get("locked") is True

    r = client.post(reverse("lock"), data={"password": "secret123"})
    assert r.status_code == 302
    assert client.session.get("locked") is None


def test_lock_post_wrong_password_stays_locked(client):
    user = UserFactory()
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    client.get(reverse("lock"))

    r = client.post(reverse("lock"), data={"password": "wrong"})
    assert r.status_code == 200
    assert b"Incorrect password" in r.content
    assert client.session.get("locked") is True


def test_locked_session_redirects_dashboard_to_lock(client):
    user = UserFactory(is_staff=True)
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    client.get(reverse("lock"))  # lock

    r = client.get("/")
    assert r.status_code == 302
    assert r.url.endswith("/lock/")


def test_locked_session_allows_logout(client):
    user = UserFactory()
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    client.get(reverse("lock"))

    # Logout (POST) should not be intercepted by the middleware
    r = client.post(reverse("logout"))
    assert r.status_code in (302, 303)


def test_locked_session_allows_landing_page(client):
    user = UserFactory()
    user.set_password("secret123")
    user.save()
    client.force_login(user)
    client.get(reverse("lock"))

    r = client.get("/landing/analytics/")
    # Marketing page is exempt — should render even when locked
    assert r.status_code == 200
