"""E2E coverage for Phase 4b Invoices.

Follows tests/e2e/test_customers.py: pytest-playwright sync API,
demo user login, fixture-created invoices for deterministic state.
"""
from decimal import Decimal

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="ApexShowcase!2026"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_invoice_list_shows_seeded_invoices(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/invoices/")
    page.locator("table tbody tr").first.wait_for(state="visible")
    # Use substring match — playwright's text=/regex/ has stricter rules than expected
    assert page.locator("a", has_text="INV-").count() > 0


def test_create_invoice_flow(page, server_url):
    from apps.customers.tests.factories import CustomerFactory
    CustomerFactory(name="E2E Invoice Customer", email="e2e-inv@example.com")

    _login(page, server_url)
    page.goto(f"{server_url}/invoices/new/")

    # Pick our fixture customer from the dropdown by visible label
    page.locator("select[name='customer']").select_option(label="E2E Invoice Customer")
    page.fill("input[name='issue_date']", "2026-06-01")
    page.fill("input[name='due_date']", "2026-06-30")
    page.fill("input[name='tax_rate']", "10")
    page.fill("input[name='items-0-description']", "Consulting hours")
    page.fill("input[name='items-0-quantity']", "4")
    page.fill("input[name='items-0-unit_price']", "150.00")

    page.click("button:has-text('Create invoice')")
    page.wait_for_url(lambda url: "/invoices/" in url and "new" not in url)

    # Total = 4 * 150 * 1.10 = 660.00
    assert page.locator("text=Consulting hours").first.is_visible()
    assert page.locator("text=$660.00").first.is_visible()


def test_transition_draft_to_sent_to_paid(page, server_url):
    from apps.customers.tests.factories import CustomerFactory
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

    c = CustomerFactory(name="Lifecycle Co", email="lifecycle@example.com")
    inv = InvoiceFactory(customer=c, status="draft")
    InvoiceItemFactory(invoice=inv, quantity=2, unit_price=Decimal("50.00"))

    _login(page, server_url)
    page.goto(f"{server_url}/invoices/{inv.pk}/")

    # Draft → Send
    page.click("button:has-text('Send')")
    page.wait_for_url(f"{server_url}/invoices/{inv.pk}/")
    page.locator(".inline-flex:has-text('Sent')").first.wait_for(state="visible", timeout=5000)

    # Sent → Mark paid
    page.click("button:has-text('Mark paid')")
    page.wait_for_url(f"{server_url}/invoices/{inv.pk}/")
    page.locator(".inline-flex:has-text('Paid')").first.wait_for(state="visible", timeout=5000)


def test_public_view_is_accessible_without_login(page, server_url):
    from apps.customers.tests.factories import CustomerFactory
    from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

    c = CustomerFactory(name="Public Co", email="public@example.com")
    inv = InvoiceFactory(customer=c, status="draft")
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("200.00"))
    inv.mark_sent()

    # No login — anonymous access via token
    page.goto(f"{server_url}/invoices/public/{inv.public_token}/")
    assert page.locator(f"text={inv.number}").first.is_visible()
    assert page.locator("text=Public Co").first.is_visible()
    assert page.locator("text=Download PDF").first.is_visible()


def test_generate_invoice_from_order(page, server_url):
    from apps.customers.tests.factories import CustomerFactory
    from apps.orders.tests.factories import OrderFactory, OrderItemFactory

    c = CustomerFactory(name="Bridge Co", email="bridge@example.com")
    order = OrderFactory(customer=c)
    OrderItemFactory(order=order, quantity=3)

    _login(page, server_url)
    page.goto(f"{server_url}/orders/{order.pk}/")
    page.click("button:has-text('Generate invoice')")

    # Lands on invoice detail
    page.wait_for_url(lambda url: "/invoices/" in url and "new" not in url)
    page.locator("h1", has_text="INV-").first.wait_for(state="visible", timeout=5000)
    # Scope to <main> to avoid matching the bell dropdown's hidden notification text
    page.locator("main").locator("text=Bridge Co").first.wait_for(state="visible", timeout=5000)
