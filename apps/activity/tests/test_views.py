import pytest

from apps.accounts.tests.factories import UserFactory
from apps.activity.tests.factories import ActivityEventFactory

pytestmark = pytest.mark.django_db


def test_list_redirects_anonymous(client):
    r = client.get("/activity/")
    assert r.status_code == 302


def test_list_renders_for_authed_user(client):
    user = UserFactory()
    client.force_login(user)
    ActivityEventFactory(actor=user, verb="created", label="A thing")
    r = client.get("/activity/")
    assert r.status_code == 200
    assert b"A thing" in r.content
    assert b"Activity" in r.content


def test_list_filters_by_category(client):
    user = UserFactory()
    client.force_login(user)
    ActivityEventFactory(category="customer", label="CustomerOne")
    ActivityEventFactory(category="invoice", label="InvoiceOne")
    r = client.get("/activity/?category=customer")
    assert b"CustomerOne" in r.content
    assert b"InvoiceOne" not in r.content


def test_list_scope_mine_filters_by_actor(client):
    me = UserFactory()
    other = UserFactory()
    client.force_login(me)
    ActivityEventFactory(actor=me, label="MyThing")
    ActivityEventFactory(actor=other, label="OtherThing")
    r = client.get("/activity/?scope=mine")
    assert b"MyThing" in r.content
    assert b"OtherThing" not in r.content


def test_list_counts_in_context(client):
    user = UserFactory()
    client.force_login(user)
    ActivityEventFactory(actor=user)
    ActivityEventFactory(actor=user)
    r = client.get("/activity/")
    counts = r.context["counts"]
    assert counts["total"] >= 2
    assert counts["mine"] >= 2
    assert counts["today"] >= 2


def test_empty_state_renders_when_no_events(client):
    """When a filter narrows results to zero, the table empty state shows
    the no-matches copy (not the no-data-yet copy — that's for an
    entirely empty table)."""
    user = UserFactory()
    client.force_login(user)
    r = client.get("/activity/?category=system")
    assert b"No matches" in r.content
