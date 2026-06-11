import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification


@pytest.fixture
def auth_client(client, db):
    user = UserFactory()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_demo_page_renders_for_authed_user(auth_client):
    client, _ = auth_client
    r = client.get(reverse("realtime:demo"))
    assert r.status_code == 200
    assert b"Realtime" in r.content
    assert b"Online now" in r.content


@pytest.mark.django_db
def test_demo_page_redirects_anon(client):
    r = client.get(reverse("realtime:demo"))
    assert r.status_code == 302
    assert "/accounts/login/" in r.url


@pytest.mark.django_db
def test_fire_endpoint_creates_notification(auth_client):
    client, user = auth_client
    r = client.post(reverse("realtime:fire_test"))
    assert r.status_code == 302
    assert Notification.objects.filter(
        recipient=user, kind="realtime_demo",
    ).exists()


@pytest.mark.django_db
def test_fire_endpoint_rejects_get(auth_client):
    client, _ = auth_client
    r = client.get(reverse("realtime:fire_test"))
    assert r.status_code == 405
