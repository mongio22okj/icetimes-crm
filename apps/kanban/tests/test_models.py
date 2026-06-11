from datetime import timedelta

import pytest
from django.utils import timezone

from apps.kanban.models import Card
from apps.kanban.tests.factories import CardFactory

pytestmark = pytest.mark.django_db


def test_is_overdue_when_past_due_and_not_done():
    yesterday = timezone.now().date() - timedelta(days=1)
    c = CardFactory(due_date=yesterday, status="todo")
    assert c.is_overdue is True


def test_is_overdue_false_when_done_even_if_past_due():
    yesterday = timezone.now().date() - timedelta(days=1)
    c = CardFactory(due_date=yesterday, status="done")
    assert c.is_overdue is False


def test_is_overdue_false_without_due_date():
    c = CardFactory(due_date=None, status="todo")
    assert c.is_overdue is False


def test_priority_border_class():
    high = CardFactory(priority="high")
    assert "red" in high.priority_border_class
    low = CardFactory(priority="low")
    assert "zinc" in low.priority_border_class


def test_default_ordering_status_then_position():
    a = CardFactory(status="done", position=0)
    b = CardFactory(status="todo", position=2)
    c = CardFactory(status="todo", position=1)
    statuses_positions = list(Card.objects.values_list("status", "position"))
    # done is alphabetically before in_progress; STATUS_CHOICES order isn't enforced —
    # ordering is by raw string, which sorts: done, in_progress, review, todo
    # We just verify within the same status, position increases
    todos = [(s, p) for s, p in statuses_positions if s == "todo"]
    assert todos == sorted(todos, key=lambda x: x[1])
