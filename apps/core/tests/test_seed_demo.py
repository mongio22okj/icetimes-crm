import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_demo_creates_demo_user():
    call_command("seed_demo")
    User = get_user_model()
    demo = User.objects.get(username=settings.DEMO_USERNAME)
    assert demo.check_password(settings.DEMO_PASSWORD)
    assert demo.is_staff is True


@pytest.mark.django_db
def test_seed_demo_creates_users_products_orders():
    call_command("seed_demo")
    User = get_user_model()
    from apps.orders.models import Order, OrderItem
    from apps.products.models import Category, Product

    # Demo user + batch users + any pre-existing test users
    assert User.objects.count() >= 15
    assert Category.objects.count() >= 3
    assert Product.objects.count() >= 20
    assert Order.objects.count() >= 30
    assert OrderItem.objects.count() >= 30  # at least 1 per order


@pytest.mark.django_db
def test_seed_demo_idempotent_demo_user():
    """Running seed_demo twice should not duplicate the demo user (or fail)."""
    call_command("seed_demo")
    User = get_user_model()
    first_count = User.objects.filter(username="demo").count()
    assert first_count == 1

    call_command("seed_demo")
    second_count = User.objects.filter(username="demo").count()
    assert second_count == 1  # Still exactly one demo user
