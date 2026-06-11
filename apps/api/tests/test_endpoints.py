"""End-to-end endpoint tests for every router."""
import json

import pytest

from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.notifications.tests.factories import NotificationFactory
from apps.products.tests.factories import ProductFactory

pytestmark = pytest.mark.django_db


# ── Customers ─────────────────────────────────────────────────────────


def test_list_customers_returns_paginated_results(client, auth_headers):
    CustomerFactory.create_batch(3)
    r = client.get("/api/v1/customers/", **auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_customers_search_filters_by_name(client, auth_headers):
    CustomerFactory(name="Northwind Trader")
    CustomerFactory(name="Acme")
    r = client.get("/api/v1/customers/?q=northwind", **auth_headers)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Northwind Trader"


def test_list_customers_status_filter(client, auth_headers):
    CustomerFactory(status="active")
    CustomerFactory(status="inactive")
    r = client.get("/api/v1/customers/?status=inactive", **auth_headers)
    items = r.json()["items"]
    assert all(c["status"] == "inactive" for c in items)


def test_list_customers_pagination_cursor(client, auth_headers):
    CustomerFactory.create_batch(40)
    r1 = client.get("/api/v1/customers/?limit=20", **auth_headers)
    page1 = r1.json()
    assert len(page1["items"]) == 20
    assert page1["next_cursor"] is not None
    r2 = client.get(f"/api/v1/customers/?limit=20&cursor={page1['next_cursor']}",
                    **auth_headers)
    page2 = r2.json()
    assert len(page2["items"]) > 0
    # Pages don't overlap
    page1_ids = {c["id"] for c in page1["items"]}
    page2_ids = {c["id"] for c in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_create_customer(client, auth_headers):
    r = client.post(
        "/api/v1/customers/",
        data=json.dumps({"name": "New Co", "email": "new@example.com"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "New Co"
    assert Customer.objects.filter(email="new@example.com").exists()


def test_create_customer_rejects_duplicate_email(client, auth_headers):
    CustomerFactory(email="taken@example.com")
    r = client.post(
        "/api/v1/customers/",
        data=json.dumps({"name": "Other", "email": "Taken@example.com"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 400


def test_get_customer_by_id(client, auth_headers):
    c = CustomerFactory()
    r = client.get(f"/api/v1/customers/{c.pk}/", **auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == c.pk


def test_get_customer_404_for_unknown(client, auth_headers):
    r = client.get("/api/v1/customers/9999/", **auth_headers)
    assert r.status_code == 404


def test_patch_customer_updates_fields(client, auth_headers):
    c = CustomerFactory(company="Old")
    r = client.patch(
        f"/api/v1/customers/{c.pk}/",
        data=json.dumps({"company": "New Co"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 200
    c.refresh_from_db()
    assert c.company == "New Co"


def test_delete_customer_soft_deletes(client, auth_headers):
    c = CustomerFactory()
    r = client.delete(f"/api/v1/customers/{c.pk}/", **auth_headers)
    assert r.status_code == 204
    # Default manager hides archived; row still exists in all_objects.
    assert not Customer.objects.filter(pk=c.pk).exists()
    assert Customer.all_objects.get(pk=c.pk).deleted_at is not None


# ── Products ──────────────────────────────────────────────────────────


def test_list_products(client, auth_headers):
    ProductFactory.create_batch(3)
    r = client.get("/api/v1/products/", **auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_create_product_requires_unique_sku(client, auth_headers):
    ProductFactory(sku="DUP-001")
    r = client.post(
        "/api/v1/products/",
        data=json.dumps({"name": "X", "sku": "DUP-001", "price": "1.00"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 400


# ── Orders ────────────────────────────────────────────────────────────


def test_list_orders_includes_items(client, auth_headers):
    from apps.orders.tests.factories import OrderFactory, OrderItemFactory
    o = OrderFactory()
    OrderItemFactory(order=o, quantity=2)
    r = client.get("/api/v1/orders/", **auth_headers)
    items = r.json()["items"]
    assert items[0]["id"] == o.pk
    assert len(items[0]["items"]) == 1


def test_patch_order_status_validates(client, auth_headers):
    from apps.orders.tests.factories import OrderFactory
    o = OrderFactory(status="pending")
    r = client.patch(
        f"/api/v1/orders/{o.pk}/status/",
        data=json.dumps({"status": "evil_status"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 400


def test_patch_order_status_updates(client, auth_headers):
    from apps.orders.tests.factories import OrderFactory
    o = OrderFactory(status="pending")
    r = client.patch(
        f"/api/v1/orders/{o.pk}/status/",
        data=json.dumps({"status": "paid"}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 200
    o.refresh_from_db()
    assert o.status == "paid"


# ── Invoices ─────────────────────────────────────────────────────────


def test_send_invoice_transitions_status(client, auth_headers):
    from apps.invoices.tests.factories import InvoiceFactory
    inv = InvoiceFactory(status="draft")
    r = client.post(f"/api/v1/invoices/{inv.pk}/send/", **auth_headers)
    assert r.status_code == 200
    inv.refresh_from_db()
    assert inv.status == "sent"


def test_send_invoice_400_for_invalid_transition(client, auth_headers):
    from apps.invoices.tests.factories import InvoiceFactory
    inv = InvoiceFactory(status="paid")  # paid → sent is invalid
    r = client.post(f"/api/v1/invoices/{inv.pk}/send/", **auth_headers)
    assert r.status_code == 400


def test_pay_invoice_transitions(client, auth_headers):
    from apps.invoices.tests.factories import InvoiceFactory
    inv = InvoiceFactory(status="sent")
    r = client.post(f"/api/v1/invoices/{inv.pk}/pay/", **auth_headers)
    assert r.status_code == 200
    inv.refresh_from_db()
    assert inv.status == "paid"


# ── Notifications ─────────────────────────────────────────────────────


def test_notifications_scoped_to_authed_user(client, user, auth_headers):
    from apps.accounts.tests.factories import UserFactory
    other = UserFactory()
    NotificationFactory(recipient=user, title="MINE")
    NotificationFactory(recipient=other, title="THEIRS")
    r = client.get("/api/v1/notifications/", **auth_headers)
    titles = [n["title"] for n in r.json()["items"]]
    assert "MINE" in titles
    assert "THEIRS" not in titles


def test_notifications_filter_by_category(client, user, auth_headers):
    NotificationFactory(recipient=user, category="billing", title="Billing-1")
    NotificationFactory(recipient=user, category="mention", title="Mention-1")
    r = client.get("/api/v1/notifications/?category=billing", **auth_headers)
    titles = [n["title"] for n in r.json()["items"]]
    assert "Billing-1" in titles
    assert "Mention-1" not in titles


def test_mark_notification_read(client, user, auth_headers):
    n = NotificationFactory(recipient=user)
    assert n.is_unread
    r = client.post(f"/api/v1/notifications/{n.pk}/read/", **auth_headers)
    assert r.status_code == 200
    n.refresh_from_db()
    assert n.read_at is not None


def test_mark_all_read(client, user, auth_headers):
    NotificationFactory.create_batch(3, recipient=user)
    r = client.post("/api/v1/notifications/read-all/", **auth_headers)
    assert r.status_code == 200
    assert r.json()["marked_read"] == 3


def test_archive_notification(client, user, auth_headers):
    n = NotificationFactory(recipient=user)
    r = client.post(f"/api/v1/notifications/{n.pk}/archive/", **auth_headers)
    assert r.status_code == 200
    n.refresh_from_db()
    assert n.archived_at is not None


# ── Webhooks ─────────────────────────────────────────────────────────


def test_create_webhook_returns_secret_once(client, user, auth_headers):
    r = client.post(
        "/api/v1/webhooks/",
        data=json.dumps({
            "url": "https://example.com/hook",
            "events": ["invoice.paid", "invoice.sent"],
        }),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["secret"]  # secret returned once on create
    # Subsequent retrieval doesn't include secret
    r2 = client.get(f"/api/v1/webhooks/{body['id']}/", **auth_headers)
    assert "secret" not in r2.json()


def test_create_webhook_requires_at_least_one_event(client, auth_headers):
    r = client.post(
        "/api/v1/webhooks/",
        data=json.dumps({"url": "https://x.example", "events": []}),
        content_type="application/json",
        **auth_headers,
    )
    assert r.status_code == 400


def test_webhooks_scoped_to_authed_user(client, user, auth_headers):
    from apps.accounts.tests.factories import UserFactory
    from apps.api.models import Webhook
    other = UserFactory()
    Webhook.objects.create(
        user=other, url="https://other.example", events="x", secret="s",
    )
    Webhook.objects.create(
        user=user, url="https://mine.example", events="x", secret="s",
    )
    r = client.get("/api/v1/webhooks/", **auth_headers)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["url"] == "https://mine.example"


def test_delete_webhook(client, user, auth_headers):
    from apps.api.models import Webhook
    w = Webhook.objects.create(
        user=user, url="https://x.example", events="invoice.paid", secret="s",
    )
    r = client.delete(f"/api/v1/webhooks/{w.pk}/", **auth_headers)
    assert r.status_code == 204
    assert not Webhook.objects.filter(pk=w.pk).exists()


# ── Swagger / OpenAPI surface ───────────────────────────────────────


def test_openapi_schema_is_served(client):
    """Swagger metadata is public — clients need to fetch it without a key."""
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Apex API"
    # Every router has at least one path documented.
    paths = schema["paths"]
    assert any("/customers" in p for p in paths)
    assert any("/orders" in p for p in paths)
    assert any("/invoices" in p for p in paths)
    assert any("/notifications" in p for p in paths)
    assert any("/webhooks" in p for p in paths)


def test_swagger_ui_renders(client):
    r = client.get("/api/v1/docs")
    assert r.status_code == 200
    assert b"swagger" in r.content.lower() or b"openapi" in r.content.lower()
