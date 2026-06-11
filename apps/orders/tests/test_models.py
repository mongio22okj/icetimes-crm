from decimal import Decimal

import pytest

from apps.customers.tests.factories import CustomerFactory
from apps.orders.models import Order, OrderItem
from apps.products.tests.factories import ProductFactory


@pytest.mark.django_db
def test_order_auto_generates_number():
    customer = CustomerFactory()
    order = Order.objects.create(customer=customer, status="pending")
    assert order.number.startswith("ORD-")
    assert len(order.number) >= 5


@pytest.mark.django_db
def test_order_total_sums_items():
    customer = CustomerFactory()
    product = ProductFactory(price=Decimal("10.00"))
    order = Order.objects.create(customer=customer, status="pending")
    OrderItem.objects.create(order=order, product=product, quantity=3, unit_price=Decimal("10.00"))
    OrderItem.objects.create(order=order, product=product, quantity=2, unit_price=Decimal("15.00"))
    assert order.total == Decimal("60.00")


@pytest.mark.django_db
def test_order_total_is_zero_when_no_items():
    customer = CustomerFactory()
    order = Order.objects.create(customer=customer, status="pending")
    assert order.total == Decimal("0")


@pytest.mark.django_db
def test_order_ordering_newest_first():
    customer = CustomerFactory()
    o1 = Order.objects.create(customer=customer, status="pending")
    o2 = Order.objects.create(customer=customer, status="pending")
    assert list(Order.objects.all()) == [o2, o1]


@pytest.mark.django_db
def test_order_item_line_total():
    from decimal import Decimal

    from apps.orders.models import OrderItem
    customer = CustomerFactory()
    product = ProductFactory()
    order = Order.objects.create(customer=customer, status="pending")
    item = OrderItem.objects.create(order=order, product=product, quantity=3, unit_price=Decimal("12.50"))
    assert item.line_total == Decimal("37.50")
