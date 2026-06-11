import pytest

from apps.events.tests.factories import EventFactory

pytestmark = pytest.mark.django_db


def test_color_returns_category_color():
    e = EventFactory(category="deadline")
    assert e.color == "#ef4444"


def test_to_fullcalendar_shape():
    e = EventFactory(title="Standup", category="meeting", all_day=False)
    payload = e.to_fullcalendar()
    assert payload["id"] == e.pk
    assert payload["title"] == "Standup"
    assert payload["color"] == "#3b82f6"
    assert payload["allDay"] is False
    assert "start" in payload and "T" in payload["start"]
    assert payload["extendedProps"]["category"] == "meeting"


def test_to_fullcalendar_all_day():
    e = EventFactory(all_day=True)
    payload = e.to_fullcalendar()
    assert payload["allDay"] is True


def test_default_ordering_by_start():
    from datetime import timedelta

    from django.utils import timezone

    from apps.events.models import Event

    now = timezone.now()
    EventFactory(start=now + timedelta(days=2), end=now + timedelta(days=2, hours=1))
    EventFactory(start=now + timedelta(hours=2), end=now + timedelta(hours=3))
    EventFactory(start=now + timedelta(days=1), end=now + timedelta(days=1, hours=1))

    starts = list(Event.objects.values_list("start", flat=True))
    assert starts == sorted(starts)
