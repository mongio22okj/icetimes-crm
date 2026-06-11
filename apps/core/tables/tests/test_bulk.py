"""Bulk-action POST dispatch tests, exercised against the wired Customer view."""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True)


def test_bulk_archive_soft_deletes_selected_rows(client, staff):
    a = CustomerFactory()
    b = CustomerFactory()
    keep = CustomerFactory()
    client.force_login(staff)
    r = client.post(reverse("customers:list"), {
        "action": "archive",
        "ids": [str(a.pk), str(b.pk)],
    })
    assert r.status_code == 302
    # Default manager hides archived rows.
    assert set(Customer.objects.values_list("pk", flat=True)) == {keep.pk}
    # all_objects can still see them with deleted_at set.
    assert Customer.all_objects.get(pk=a.pk).deleted_at is not None


def test_bulk_mark_inactive_updates_status(client, staff):
    a = CustomerFactory(status="active")
    b = CustomerFactory(status="active")
    client.force_login(staff)
    r = client.post(reverse("customers:list"), {
        "action": "mark_inactive",
        "ids": [str(a.pk), str(b.pk)],
    })
    assert r.status_code == 302
    assert Customer.objects.get(pk=a.pk).status == "inactive"
    assert Customer.objects.get(pk=b.pk).status == "inactive"


def test_bulk_mark_active_reverses_inactive(client, staff):
    c = CustomerFactory(status="inactive")
    client.force_login(staff)
    client.post(reverse("customers:list"), {
        "action": "mark_active",
        "ids": [str(c.pk)],
    })
    assert Customer.objects.get(pk=c.pk).status == "active"


def test_bulk_unknown_action_returns_400(client, staff):
    c = CustomerFactory()
    client.force_login(staff)
    r = client.post(reverse("customers:list"), {
        "action": "drop_database",
        "ids": [str(c.pk)],
    })
    assert r.status_code == 400


def test_bulk_no_ids_returns_400(client, staff):
    client.force_login(staff)
    r = client.post(reverse("customers:list"), {"action": "archive"})
    assert r.status_code == 400


def test_bulk_post_requires_auth(client):
    r = client.post(reverse("customers:list"), {
        "action": "archive",
        "ids": ["1"],
    })
    # Anonymous → LoginRequiredMixin redirects
    assert r.status_code in (302, 301)


def test_bulk_post_requires_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    c = CustomerFactory()
    r = client.post(reverse("customers:list"), {
        "action": "archive",
        "ids": [str(c.pk)],
    })
    # StaffRequiredMixin → 403
    assert r.status_code == 403


def test_bulk_action_emits_success_message(client, staff):
    a = CustomerFactory()
    client.force_login(staff)
    r = client.post(reverse("customers:list"), {
        "action": "mark_inactive",
        "ids": [str(a.pk)],
    }, follow=True)
    body = r.content.decode()
    assert "Marked 1 customers as inactive" in body
