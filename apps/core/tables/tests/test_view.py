"""TableView round-trip tests using the wired-up Customer list view."""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.core.models import UserPreference
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True)


def test_list_renders_and_uses_full_template(client, staff):
    CustomerFactory.create_batch(3)
    client.force_login(staff)
    r = client.get(reverse("customers:list"))
    assert r.status_code == 200
    assert "table-customers" in r.content.decode()
    # Full page (with header), not the partial.
    assert "<html" in r.content.decode().lower()


def test_list_partial_request_renders_just_the_table(client, staff):
    CustomerFactory.create_batch(3)
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_partial=table")
    body = r.content.decode()
    assert r.status_code == 200
    assert "table-customers" in body
    # Partial — no full page chrome.
    assert "<html" not in body.lower()
    assert "</body>" not in body.lower()


def test_list_partial_request_via_hx_request_header(client, staff):
    CustomerFactory.create_batch(2)
    client.force_login(staff)
    r = client.get(reverse("customers:list"), headers={"HX-Request": "true"})
    body = r.content.decode()
    assert r.status_code == 200
    assert "table-customers" in body
    assert "<html" not in body.lower()


def test_search_filters_results(client, staff):
    CustomerFactory(name="Northwind Trader")
    CustomerFactory(name="Acme")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?q=northwind&_partial=table")
    body = r.content.decode()
    assert "Northwind" in body
    assert "Acme" not in body


def test_status_filter_narrows_results(client, staff):
    active = CustomerFactory(status="active", name="ActivePerson")
    inactive = CustomerFactory(status="inactive", name="InactivePerson")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?status=inactive&_partial=table")
    body = r.content.decode()
    assert "InactivePerson" in body
    assert "ActivePerson" not in body


def test_sort_param_applied(client, staff):
    CustomerFactory(name="Aardvark")
    CustomerFactory(name="Zebra")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?sort=name&_partial=table")
    body = r.content.decode()
    # Aardvark should appear before Zebra in the rendered HTML
    assert body.index("Aardvark") < body.index("Zebra")


def test_sort_param_descending(client, staff):
    CustomerFactory(name="Aardvark")
    CustomerFactory(name="Zebra")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?sort=-name&_partial=table")
    body = r.content.decode()
    assert body.index("Zebra") < body.index("Aardvark")


def test_unknown_sort_param_does_not_500(client, staff):
    CustomerFactory()
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?sort=evil_field&_partial=table")
    assert r.status_code == 200


def test_pagination_returns_correct_count(client, staff):
    CustomerFactory.create_batch(30)  # > page_size of 25
    client.force_login(staff)
    r = client.get(reverse("customers:list"))
    body = r.content.decode()
    assert "30 total" in body  # pagination strip text


def test_save_columns_redirects_and_persists(client, staff):
    client.force_login(staff)
    r = client.get(
        reverse("customers:list") + "?_save_columns=1&columns=name,email"
    )
    assert r.status_code == 302
    # Stored pref includes pinned columns auto-merged in
    pref = UserPreference.objects.get(user=staff, key="table.customers.visible_columns")
    assert "name" in pref.value["columns"]
    assert "email" in pref.value["columns"]


def test_visibility_pref_filters_columns_in_render(client, staff):
    """If user saved {name only}, the company column should not appear."""
    UserPreference.objects.create(
        user=staff,
        key="table.customers.visible_columns",
        value={"columns": ["name"]},  # name is pinned anyway; intentional minimum
    )
    CustomerFactory(name="Bob", company="Visible Inc")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?_partial=table")
    body = r.content.decode()
    # Name is rendered, company column is hidden
    assert "Bob" in body
    assert "Visible Inc" not in body


def test_empty_state_no_data(client, staff):
    client.force_login(staff)
    r = client.get(reverse("customers:list"))
    body = r.content.decode()
    assert "No rows yet" in body or "No matches" in body  # fallback if seed exists


def test_empty_state_no_results_with_filter(client, staff):
    CustomerFactory(name="Existing")
    client.force_login(staff)
    r = client.get(reverse("customers:list") + "?q=nope_no_match")
    body = r.content.decode()
    assert "No matches" in body
