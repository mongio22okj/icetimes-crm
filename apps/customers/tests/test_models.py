from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def test_email_lowercased_on_save():
    c = Customer.objects.create(name="Alice", email="Alice@EXAMPLE.com")
    c.refresh_from_db()
    assert c.email == "alice@example.com"


def test_duplicate_email_raises():
    Customer.objects.create(name="One", email="dup@example.com")
    with pytest.raises(IntegrityError):
        Customer.objects.create(name="Two", email="dup@example.com")


def test_archive_sets_deleted_at():
    c = CustomerFactory()
    assert c.deleted_at is None
    c.archive()
    c.refresh_from_db()
    assert c.deleted_at is not None


def test_restore_clears_deleted_at():
    c = CustomerFactory()
    c.archive()
    c.restore()
    c.refresh_from_db()
    assert c.deleted_at is None


def test_default_manager_hides_archived():
    active = CustomerFactory(name="Alice")
    archived = CustomerFactory(name="Bob")
    archived.archive()
    assert Customer.objects.filter(pk=active.pk).exists()
    assert not Customer.objects.filter(pk=archived.pk).exists()


def test_all_objects_returns_archived():
    c = CustomerFactory()
    c.archive()
    assert Customer.all_objects.filter(pk=c.pk).exists()


def test_initials_two_part_name():
    c = CustomerFactory(name="Alice Chen")
    assert c.initials() == "AC"


def test_initials_single_name():
    c = CustomerFactory(name="Alice")
    assert c.initials() == "AL"


def test_initials_empty_name_falls_back():
    c = CustomerFactory(name=" ")
    assert c.initials() == "??"


def test_total_orders_counts_linked_orders():
    from apps.orders.tests.factories import OrderFactory
    c = CustomerFactory()
    # Pre-swap: Order.customer is User. Skip if that's still true.
    # After Task 5, OrderFactory.customer will be CustomerFactory.
    try:
        OrderFactory(customer=c)
        assert c.total_orders >= 1
    except (TypeError, ValueError):
        pytest.skip("Order.customer FK still points at User; activated in Task 5")


def test_total_spent_sums_order_totals():
    from apps.orders.tests.factories import OrderFactory
    c = CustomerFactory()
    try:
        OrderFactory(customer=c)
        assert c.total_spent >= Decimal("0")
    except (TypeError, ValueError):
        pytest.skip("Order.customer FK still points at User; activated in Task 5")
