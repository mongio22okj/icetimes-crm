import pytest

from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


def test_default_is_unread():
    n = NotificationFactory()
    assert n.read_at is None
    assert n.is_unread is True


def test_mark_read_sets_read_at():
    n = NotificationFactory()
    n.mark_read()
    assert n.read_at is not None
    assert n.is_unread is False


def test_mark_read_is_idempotent():
    n = NotificationFactory()
    n.mark_read()
    first_read = n.read_at
    n.mark_read()
    n.refresh_from_db()
    assert n.read_at == first_read


def test_unread_queryset_excludes_read():
    a = NotificationFactory()
    b = NotificationFactory()
    b.mark_read()
    unread = Notification.objects.unread()
    assert a in unread
    assert b not in unread


def test_read_queryset_excludes_unread():
    a = NotificationFactory()
    b = NotificationFactory()
    b.mark_read()
    read = Notification.objects.read()
    assert a not in read
    assert b in read


def test_default_ordering_is_newest_first():
    older = NotificationFactory()
    newer = NotificationFactory()
    ordered = list(Notification.objects.all())
    assert ordered[0] == newer
    assert ordered[1] == older
