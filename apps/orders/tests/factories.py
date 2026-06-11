from decimal import Decimal

import factory

from apps.customers.tests.factories import CustomerFactory
from apps.orders.models import Order, OrderItem
from apps.products.tests.factories import ProductFactory


class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order

    customer = factory.SubFactory(CustomerFactory)
    status = "pending"


class OrderItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OrderItem

    order = factory.SubFactory(OrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = factory.Faker("pyint", min_value=1, max_value=10)
    unit_price = factory.LazyAttribute(lambda o: Decimal("19.99"))
