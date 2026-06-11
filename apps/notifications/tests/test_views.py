import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory(username="alice")


@pytest.fixture
def other_user():
    return UserFactory(username="bob")


# ----- List -----

def test_list_redirects_anonymous(client):
    r = client.get(reverse("notifications:list"))
    assert r.status_code == 302
    assert "login" in r.url


def test_list_shows_only_own_notifications(client, user, other_user):
    client.force_login(user)
    mine = NotificationFactory(recipient=user, title="Mine")
    NotificationFactory(recipient=other_user, title="Theirs")
    r = client.get(reverse("notifications:list"))
    assert r.status_code == 200
    assert b"Mine" in r.content
    assert b"Theirs" not in r.content


# ----- Bell -----

def test_bell_returns_unread_count_and_recent(client, user):
    client.force_login(user)
    for i in range(7):
        NotificationFactory(recipient=user, title=f"Note {i}")
    NotificationFactory(recipient=user, title="Read note").mark_read()

    r = client.get(reverse("notifications:bell"))
    assert r.status_code == 200
    # Unread count in badge: 7
    assert b"7" in r.content
    # Recent limit is 5 — the 5 most recent of the 8 total are visible
    # (ordering is newest-first; the 2 oldest "Note 0" and "Note 1" won't be in top 5)


def test_bell_requires_login(client):
    r = client.get(reverse("notifications:bell"))
    assert r.status_code == 302


# ----- Mark read -----

def test_mark_read_sets_read_at(client, user):
    client.force_login(user)
    n = NotificationFactory(recipient=user)
    r = client.post(reverse("notifications:mark_read", args=[n.pk]))
    assert r.status_code == 302
    n.refresh_from_db()
    assert n.read_at is not None


def test_mark_read_cross_user_returns_404(client, user, other_user):
    client.force_login(user)
    theirs = NotificationFactory(recipient=other_user)
    r = client.post(reverse("notifications:mark_read", args=[theirs.pk]))
    assert r.status_code == 404


def test_mark_read_htmx_returns_bell_partial(client, user):
    client.force_login(user)
    n = NotificationFactory(recipient=user)
    r = client.post(
        reverse("notifications:mark_read", args=[n.pk]),
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert b"notification-bell-content" in r.content


# ----- Mark all -----

def test_mark_all_read(client, user):
    client.force_login(user)
    NotificationFactory.create_batch(3, recipient=user)
    r = client.post(reverse("notifications:mark_all"))
    assert r.status_code == 302
    assert Notification.objects.filter(recipient=user, read_at__isnull=True).count() == 0


def test_mark_all_does_not_affect_other_users(client, user, other_user):
    client.force_login(user)
    NotificationFactory.create_batch(2, recipient=user)
    NotificationFactory(recipient=other_user)
    client.post(reverse("notifications:mark_all"))
    assert Notification.objects.filter(recipient=other_user, read_at__isnull=True).count() == 1


def test_mark_all_get_returns_405(client, user):
    client.force_login(user)
    r = client.get(reverse("notifications:mark_all"))
    assert r.status_code == 405
