from decimal import Decimal

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.customers.tests.factories import CustomerFactory
from apps.orders.models import Order
from apps.orders.tests.factories import OrderFactory, OrderItemFactory
from apps.products.tests.factories import ProductFactory


@pytest.mark.django_db
def test_order_list_requires_login(client):
    response = client.get("/orders/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_order_list_renders_rows(client):
    client.force_login(UserFactory())
    OrderFactory.create_batch(3)
    response = client.get("/orders/")
    assert response.status_code == 200
    assert response.content.count(b"ORD-") >= 3


@pytest.mark.django_db
def test_order_list_paginates(client):
    client.force_login(UserFactory())
    OrderFactory.create_batch(25)
    response = client.get("/orders/")
    assert response.context["page_obj"].paginator.count == 25


@pytest.mark.django_db
def test_order_detail_shows_items_and_total(client):
    client.force_login(UserFactory())
    order = OrderFactory()
    OrderItemFactory(order=order, quantity=2, unit_price=Decimal("10.00"))
    OrderItemFactory(order=order, quantity=3, unit_price=Decimal("5.00"))
    response = client.get(f"/orders/{order.pk}/")
    assert response.status_code == 200
    # Total = 2*10 + 3*5 = 35
    assert b"35" in response.content


@pytest.mark.django_db
def test_order_create_get_renders_form_and_empty_formset(client):
    client.force_login(UserFactory())
    response = client.get("/orders/new/")
    assert response.status_code == 200
    assert b"items-TOTAL_FORMS" in response.content  # formset management form


@pytest.mark.django_db
def test_order_create_post_with_one_item_persists(client):
    client.force_login(UserFactory())
    customer = CustomerFactory()
    product = ProductFactory(price=Decimal("15.00"))

    response = client.post("/orders/new/", {
        "customer": customer.pk,
        "status": "pending",
        # formset management form
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        # one item row
        "items-0-product": product.pk,
        "items-0-quantity": "2",
        "items-0-unit_price": "15.00",
    })
    assert response.status_code == 302
    order = Order.objects.latest("created_at")
    assert order.items.count() == 1
    assert order.total == Decimal("30.00")


@pytest.mark.django_db
def test_order_edit_updates_status(client):
    client.force_login(UserFactory())
    order = OrderFactory()
    item = OrderItemFactory(order=order)

    response = client.post(f"/orders/{order.pk}/edit/", {
        "customer": order.customer.pk,
        "status": "paid",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "1",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-id": str(item.pk),
        "items-0-order": str(order.pk),
        "items-0-product": str(item.product.pk),
        "items-0-quantity": str(item.quantity),
        "items-0-unit_price": str(item.unit_price),
    })
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == "paid"
