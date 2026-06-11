"""Phase #4 polish — global search endpoint smoke tests."""
import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_search_redirects_anonymous(client):
    r = client.get(reverse("search"), {"q": "alice"})
    # login_required → 302 to login
    assert r.status_code == 302


def test_search_short_query_returns_empty_groups(client):
    user = UserFactory(is_staff=True)
    client.force_login(user)
    r = client.get(reverse("search"), {"q": "a"})
    assert r.status_code == 200
    assert r.json()["groups"] == []


def test_search_finds_customers_for_staff(client):
    from apps.customers.tests.factories import CustomerFactory
    CustomerFactory(name="Alpha Corp", email="hello@alpha.example")
    CustomerFactory(name="Beta LLC", email="contact@beta.example")
    user = UserFactory(is_staff=True)
    client.force_login(user)
    r = client.get(reverse("search"), {"q": "Alpha"})
    data = r.json()
    customer_groups = [g for g in data["groups"] if g["label"] == "Customers"]
    assert customer_groups, "expected a Customers group"
    labels = [it["label"] for it in customer_groups[0]["items"]]
    assert "Alpha Corp" in labels
    assert "Beta LLC" not in labels


def test_search_finds_invoices(client):
    from apps.customers.tests.factories import CustomerFactory
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory
    c = CustomerFactory(name="Findme Inc")
    inv = InvoiceFactory(customer=c)
    InvoiceItemFactory(invoice=inv)
    user = UserFactory(is_staff=True)
    client.force_login(user)
    r = client.get(reverse("search"), {"q": "Findme"})
    data = r.json()
    invoice_groups = [g for g in data["groups"] if g["label"] == "Invoices"]
    assert invoice_groups
    assert any(inv.number in it["label"] for it in invoice_groups[0]["items"])


def test_search_omits_staff_only_groups_for_non_staff(client):
    from apps.customers.tests.factories import CustomerFactory
    CustomerFactory(name="Hidden Corp")
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("search"), {"q": "Hidden"})
    data = r.json()
    # Customers group requires staff — should not appear
    assert not any(g["label"] == "Customers" for g in data["groups"])


def test_search_caps_at_5_per_group(client):
    from apps.customers.tests.factories import CustomerFactory
    for i in range(8):
        CustomerFactory(name=f"BigCo {i}")
    user = UserFactory(is_staff=True)
    client.force_login(user)
    r = client.get(reverse("search"), {"q": "BigCo"})
    data = r.json()
    customers = [g for g in data["groups"] if g["label"] == "Customers"][0]
    assert len(customers["items"]) == 5
