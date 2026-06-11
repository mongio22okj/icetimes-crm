import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.kanban.models import Card
from apps.kanban.tests.factories import CardFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user():
    return UserFactory(is_staff=True)


# ----- Access -----

def test_board_redirects_anonymous(client):
    r = client.get(reverse("kanban:board"))
    assert r.status_code == 302


def test_board_forbidden_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("kanban:board"))
    assert r.status_code == 403


def test_board_groups_cards_by_status(client, staff_user):
    client.force_login(staff_user)
    CardFactory(status="todo", title="t1")
    CardFactory(status="done", title="d1")
    r = client.get(reverse("kanban:board"))
    assert r.status_code == 200
    columns = r.context["columns"]
    by_key = {c["key"]: c for c in columns}
    todo_titles = [c.title for c in by_key["todo"]["cards"]]
    done_titles = [c.title for c in by_key["done"]["cards"]]
    assert "t1" in todo_titles
    assert "d1" in done_titles
    assert "d1" not in todo_titles


# ----- Create -----

def test_create_assigns_creator_and_appends_position(client, staff_user):
    other = UserFactory(is_staff=True)
    client.force_login(staff_user)
    CardFactory(status="todo", position=0)
    CardFactory(status="todo", position=1)

    payload = {
        "title": "New",
        "description": "",
        "status": "todo",
        "priority": "med",
        "assignee": other.pk,
        "due_date": "",
    }
    r = client.post(reverse("kanban:create"), data=payload)
    assert r.status_code == 302
    new = Card.objects.get(title="New")
    assert new.created_by == staff_user
    assert new.position == 2  # appended at end


# ----- Move -----

def test_move_across_columns_shifts_destination(client, staff_user):
    client.force_login(staff_user)
    a = CardFactory(status="todo", position=0, title="A")
    b = CardFactory(status="todo", position=1, title="B")
    c = CardFactory(status="done", position=0, title="C")

    # Move B to done at position 0 — should push C to position 1
    r = client.post(reverse("kanban:move", args=[b.pk]), data={
        "to": "done", "position": "0",
    })
    assert r.status_code == 302
    b.refresh_from_db()
    c.refresh_from_db()
    assert b.status == "done"
    assert b.position == 0
    assert c.position == 1


def test_move_invalid_status_400(client, staff_user):
    client.force_login(staff_user)
    card = CardFactory(status="todo")
    r = client.post(reverse("kanban:move", args=[card.pk]), data={
        "to": "bogus", "position": "0",
    })
    assert r.status_code == 400


def test_move_within_column_reorders(client, staff_user):
    client.force_login(staff_user)
    a = CardFactory(status="todo", position=0, title="A")
    b = CardFactory(status="todo", position=1, title="B")
    cc = CardFactory(status="todo", position=2, title="C")

    # Move A to position 2 (end)
    r = client.post(reverse("kanban:move", args=[a.pk]), data={
        "to": "todo", "position": "2",
    })
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    cc.refresh_from_db()
    # New order should be B, C, A
    by_pos = sorted([(b.position, b.title), (cc.position, cc.title), (a.position, a.title)])
    assert [t for _, t in by_pos] == ["B", "C", "A"]


def test_move_htmx_returns_204(client, staff_user):
    client.force_login(staff_user)
    card = CardFactory(status="todo")
    r = client.post(
        reverse("kanban:move", args=[card.pk]),
        data={"to": "done", "position": "0"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 204


# ----- Delete -----

def test_delete_removes_card(client, staff_user):
    client.force_login(staff_user)
    card = CardFactory()
    r = client.post(reverse("kanban:delete", args=[card.pk]))
    assert r.status_code == 302
    assert not Card.objects.filter(pk=card.pk).exists()
