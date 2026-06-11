import pytest

from apps.activity.models import ActivityEvent
from apps.activity.services import record
from apps.activity.tests.factories import ActivityEventFactory

pytestmark = pytest.mark.django_db


def test_record_creates_event():
    e = record(category="system", verb="did", label="something")
    assert e is not None
    assert ActivityEvent.objects.filter(pk=e.pk).exists()


def test_record_handles_missing_actor():
    e = record(category="system", verb="happened", label="auto thing")
    assert e.actor is None


def test_default_icon_falls_back_to_category():
    e = ActivityEventFactory(category="customer", icon="")
    assert e.default_icon == "user-plus"


def test_default_icon_uses_explicit_when_set():
    e = ActivityEventFactory(category="customer", icon="rocket")
    assert e.default_icon == "rocket"


def test_str_includes_actor_verb_label():
    user = ActivityEventFactory(verb="hugged", label="the world").actor
    e = ActivityEventFactory(actor=user, verb="hugged", label="the world")
    assert "hugged" in str(e)
    assert "the world" in str(e)


def test_ordering_is_newest_first():
    a = ActivityEventFactory(label="first")
    b = ActivityEventFactory(label="second")
    events = list(ActivityEvent.objects.all())
    assert events[0] == b
    assert events[1] == a
