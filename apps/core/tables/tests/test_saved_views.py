"""Saved-view round-trip tests via the Customer table."""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.core.models import SavedView
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True)


def test_save_view_persists_current_params(client, staff):
    client.force_login(staff)
    r = client.get(
        reverse("customers:list")
        + "?status=inactive&sort=name&_view_action=save&_view_name=Inactive%20by%20name"
    )
    assert r.status_code == 302
    view = SavedView.objects.get(user=staff, table_key="customers", name="Inactive by name")
    # Stored params exclude our action machinery + page + _partial.
    assert view.params.get("status") == ["inactive"]
    assert view.params.get("sort") == ["name"]
    assert "_view_action" not in view.params


def test_save_view_without_name_returns_400(client, staff):
    client.force_login(staff)
    r = client.get(
        reverse("customers:list") + "?status=inactive&_view_action=save&_view_name="
    )
    assert r.status_code == 400


def test_save_view_overwrites_existing_name(client, staff):
    client.force_login(staff)
    client.get(
        reverse("customers:list")
        + "?status=inactive&_view_action=save&_view_name=My%20View"
    )
    client.get(
        reverse("customers:list")
        + "?status=active&_view_action=save&_view_name=My%20View"
    )
    view = SavedView.objects.get(user=staff, table_key="customers", name="My View")
    assert view.params.get("status") == ["active"]
    assert SavedView.objects.filter(user=staff, table_key="customers").count() == 1


def test_set_default_view_clears_other_defaults(client, staff):
    a = SavedView.objects.create(user=staff, table_key="customers", name="A", is_default=True)
    b = SavedView.objects.create(user=staff, table_key="customers", name="B")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + f"?_view_action=default&_view_id={b.pk}")
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.is_default is False
    assert b.is_default is True


def test_clear_default_clears_all(client, staff):
    SavedView.objects.create(user=staff, table_key="customers", name="A", is_default=True)
    client.force_login(staff)
    client.get(reverse("customers:list") + "?_view_action=clear_default")
    assert not SavedView.objects.filter(
        user=staff, table_key="customers", is_default=True,
    ).exists()


def test_delete_view(client, staff):
    v = SavedView.objects.create(user=staff, table_key="customers", name="X")
    client.force_login(staff)
    client.get(reverse("customers:list") + f"?_view_action=delete&_view_id={v.pk}")
    assert not SavedView.objects.filter(pk=v.pk).exists()


def test_default_view_applied_on_bare_visit(client, staff):
    """Visiting /customers/ with no params and a default view set redirects
    to the URL with that view's params applied.
    """
    SavedView.objects.create(
        user=staff, table_key="customers", name="Inactive",
        is_default=True, params={"status": ["inactive"]},
    )
    client.force_login(staff)
    r = client.get(reverse("customers:list"))
    assert r.status_code == 302
    assert "status=inactive" in r["Location"]


def test_default_view_not_applied_when_params_present(client, staff):
    """If the request already has params, the default view should NOT
    redirect (the user is intentionally overriding)."""
    SavedView.objects.create(
        user=staff, table_key="customers", name="Inactive",
        is_default=True, params={"status": ["inactive"]},
    )
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?status=active")
    assert r.status_code == 200


def test_default_view_not_applied_to_partial_requests(client, staff):
    """HTMX swaps must not get caught in the default-view redirect."""
    SavedView.objects.create(
        user=staff, table_key="customers", name="Inactive",
        is_default=True, params={"status": ["inactive"]},
    )
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_partial=table")
    assert r.status_code == 200


def test_unknown_view_action_returns_400(client, staff):
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_view_action=evil")
    assert r.status_code == 400


def test_users_dont_see_each_others_saved_views(client, staff):
    other = UserFactory(is_staff=True)
    SavedView.objects.create(user=other, table_key="customers", name="Their view")
    CustomerFactory()
    client.force_login(staff)
    r = client.get(reverse("customers:list"))
    body = r.content.decode()
    assert "Their view" not in body
