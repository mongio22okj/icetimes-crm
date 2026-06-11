import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event
from apps.events.tests.factories import EventFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice():
    return UserFactory(username="alice", is_staff=True)


@pytest.fixture
def bob():
    return UserFactory(username="bob", is_staff=True)


# ----- Calendar page -----

def test_calendar_redirects_anonymous(client):
    r = client.get(reverse("events:calendar"))
    assert r.status_code == 302


def test_calendar_forbidden_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("events:calendar"))
    assert r.status_code == 403


def test_calendar_ok_for_staff(client, alice):
    client.force_login(alice)
    r = client.get(reverse("events:calendar"))
    assert r.status_code == 200


# ----- JSON endpoint -----

def test_json_returns_only_owner_events(client, alice, bob):
    EventFactory(owner=alice, title="alice_event")
    EventFactory(owner=bob, title="bob_event")
    client.force_login(alice)
    r = client.get(reverse("events:event_json"))
    assert r.status_code == 200
    payload = json.loads(r.content)
    titles = [e["title"] for e in payload]
    assert "alice_event" in titles
    assert "bob_event" not in titles


def test_json_filters_by_range(client, alice):
    now = timezone.now()
    in_range = EventFactory(owner=alice, start=now, end=now + timedelta(hours=1))
    out_of_range = EventFactory(
        owner=alice,
        start=now + timedelta(days=30),
        end=now + timedelta(days=30, hours=1),
    )
    client.force_login(alice)
    # Pass query params as a dict so URL encoding is correct
    r = client.get(
        reverse("events:event_json"),
        {"start": now.isoformat(), "end": (now + timedelta(days=2)).isoformat()},
    )
    payload = json.loads(r.content)
    ids = [e["id"] for e in payload]
    assert in_range.pk in ids
    assert out_of_range.pk not in ids


# ----- Create -----

def test_create_assigns_owner_to_current_user(client, alice):
    client.force_login(alice)
    now = timezone.now()
    payload = {
        "title": "Sync",
        "description": "weekly",
        "start": now.strftime("%Y-%m-%dT%H:%M"),
        "end": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "category": "meeting",
    }
    r = client.post(reverse("events:create"), data=payload)
    assert r.status_code == 302
    e = Event.objects.get()
    assert e.owner == alice


def test_create_rejects_end_before_start(client, alice):
    client.force_login(alice)
    now = timezone.now()
    payload = {
        "title": "Backwards",
        "start": (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        "end": now.strftime("%Y-%m-%dT%H:%M"),
        "category": "meeting",
    }
    r = client.post(reverse("events:create"), data=payload)
    assert r.status_code == 200
    assert b"End must be after start" in r.content


# ----- Edit / Delete -----

def test_edit_404_for_other_users_event(client, alice, bob):
    e = EventFactory(owner=bob)
    client.force_login(alice)
    r = client.get(reverse("events:edit", args=[e.pk]))
    assert r.status_code == 404


def test_delete_removes_own_event(client, alice):
    e = EventFactory(owner=alice)
    client.force_login(alice)
    r = client.post(reverse("events:delete", args=[e.pk]))
    assert r.status_code == 302
    assert not Event.objects.filter(pk=e.pk).exists()


def test_delete_404_for_other_users_event(client, alice, bob):
    e = EventFactory(owner=bob)
    client.force_login(alice)
    r = client.post(reverse("events:delete", args=[e.pk]))
    assert r.status_code == 404
    assert Event.objects.filter(pk=e.pk).exists()
