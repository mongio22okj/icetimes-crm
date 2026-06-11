from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.customers.tests.factories import CustomerFactory
from apps.invoices.models import Invoice
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user():
    return UserFactory(is_staff=True)


@pytest.fixture
def regular_user():
    return UserFactory(is_staff=False)


# ----- Access control -----

def test_list_redirects_anonymous(client):
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 302
    assert "login" in r.url


def test_list_forbidden_for_non_staff(client, regular_user):
    client.force_login(regular_user)
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 403


def test_list_ok_for_staff(client, staff_user):
    client.force_login(staff_user)
    InvoiceFactory.create_batch(3)
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 200
    assert b"INV-" in r.content


# ----- Create -----

def test_create_invoice_flow(client, staff_user):
    client.force_login(staff_user)
    customer = CustomerFactory()
    payload = {
        "customer": customer.pk,
        "order": "",
        "issue_date": date(2026, 6, 1).isoformat(),
        "due_date": date(2026, 6, 30).isoformat(),
        "tax_rate": "10.00",
        "notes": "Thanks!",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "1",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-description": "Consulting",
        "items-0-quantity": "2",
        "items-0-unit_price": "150.00",
    }
    r = client.post(reverse("invoices:create"), data=payload)
    assert r.status_code == 302
    inv = Invoice.objects.get()
    assert inv.number.startswith("INV-2026-")
    assert inv.items.count() == 1
    assert inv.subtotal == Decimal("300.00")


# ----- Detail -----

def test_detail_ok_for_staff(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("50.00"))
    r = client.get(reverse("invoices:detail", args=[inv.pk]))
    assert r.status_code == 200
    assert inv.number.encode() in r.content


# ----- Edit -----

def test_edit_draft_allowed(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:edit", args=[inv.pk]))
    assert r.status_code == 200


def test_edit_sent_forbidden(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.get(reverse("invoices:edit", args=[inv.pk]))
    assert r.status_code == 403


# ----- Delete -----

def test_delete_draft_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.post(reverse("invoices:delete", args=[inv.pk]))
    assert r.status_code == 302
    assert not Invoice.objects.filter(pk=inv.pk).exists()


def test_delete_sent_forbidden(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:delete", args=[inv.pk]))
    assert r.status_code == 403
    assert Invoice.objects.filter(pk=inv.pk).exists()


# ----- HTMX row add -----

def test_add_row_returns_blank_row(client, staff_user):
    client.force_login(staff_user)
    r = client.get(reverse("invoices:add_row") + "?index=2")
    assert r.status_code == 200
    assert b"items-2-description" in r.content


# ----- Transitions -----

def test_send_draft_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    r = client.post(reverse("invoices:send", args=[inv.pk]))
    assert r.status_code == 302
    inv.refresh_from_db()
    assert inv.status == "sent"


def test_send_already_sent_flashes_error(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:send", args=[inv.pk]), follow=True)
    assert r.status_code == 200
    msgs = list(r.context["messages"])
    assert any("Cannot transition" in str(m) for m in msgs)


def test_pay_sent_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    client.post(reverse("invoices:pay", args=[inv.pk]))
    inv.refresh_from_db()
    assert inv.status == "paid"


def test_void_sent_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    client.post(reverse("invoices:void", args=[inv.pk]))
    inv.refresh_from_db()
    assert inv.status == "void"


def test_pay_draft_flashes_error(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.post(reverse("invoices:pay", args=[inv.pk]), follow=True)
    inv.refresh_from_db()
    assert inv.status == "draft"
    msgs = list(r.context["messages"])
    assert any("Cannot transition" in str(m) for m in msgs)


def test_transition_get_returns_405(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:send", args=[inv.pk]))
    assert r.status_code == 405


# ----- Public views -----

def test_public_view_on_sent_invoice_ok(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 200
    assert inv.number.encode() in r.content


def test_public_view_on_draft_404(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 404


def test_public_view_no_auth_required(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    # No client.force_login
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 200


def test_public_pdf_on_draft_404(client):
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:public_pdf", args=[inv.public_token]))
    assert r.status_code == 404


# ----- Order bridge -----

def test_generate_invoice_from_order(client, staff_user):
    from apps.orders.tests.factories import OrderFactory, OrderItemFactory
    client.force_login(staff_user)
    order = OrderFactory()
    OrderItemFactory(order=order, quantity=2)
    r = client.post(reverse("orders:generate_invoice", args=[order.pk]))
    assert r.status_code == 302
    inv = Invoice.objects.get()
    assert inv.order == order
    assert inv.customer == order.customer
    assert inv.items.count() == 1


def test_generate_invoice_requires_staff(client, regular_user):
    from apps.orders.tests.factories import OrderFactory
    client.force_login(regular_user)
    order = OrderFactory()
    r = client.post(reverse("orders:generate_invoice", args=[order.pk]))
    assert r.status_code == 403
    assert Invoice.objects.count() == 0
