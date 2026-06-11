import pytest

from apps.accounts.tests.factories import UserFactory
from apps.billing.models import PaymentMethod, Subscription

pytestmark = pytest.mark.django_db


def test_str_returns_brand_and_last4():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="pro")
    pm = PaymentMethod.objects.create(
        subscription=sub, brand="visa", last4="4242",
        exp_month=12, exp_year=2030,
    )
    assert str(pm) == "Visa •••• 4242"


def test_subscription_plan_limits_known_per_tier():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="starter")
    assert sub.limits["seats"] == 5


def test_usage_percent_capped_at_100():
    u = UserFactory()
    sub = Subscription.objects.create(
        user=u, plan="free",  # free.api_calls = 1000
        usage_api_calls=99999,
    )
    assert sub.usage_percent("api_calls") == 100


def test_usage_percent_zero_for_unmetered():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="free", usage_api_calls=0)
    assert sub.usage_percent("api_calls") == 0


def test_cancel_sets_status_and_timestamp():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="pro", status="active")
    sub.cancel()
    sub.refresh_from_db()
    assert sub.status == "canceled"
    assert sub.canceled_at is not None


def test_reactivate_clears_cancellation():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="pro", status="active")
    sub.cancel()
    sub.reactivate()
    sub.refresh_from_db()
    assert sub.status == "active"
    assert sub.canceled_at is None


def test_setting_default_pm_demotes_others():
    u = UserFactory()
    sub = Subscription.objects.create(user=u, plan="pro")
    a = PaymentMethod.objects.create(
        subscription=sub, brand="visa", last4="4242",
        exp_month=1, exp_year=2030, is_default=True,
    )
    b = PaymentMethod.objects.create(
        subscription=sub, brand="mastercard", last4="5151",
        exp_month=2, exp_year=2030, is_default=True,
    )
    a.refresh_from_db()
    assert a.is_default is False
    assert b.is_default is True


def test_usage_percent_properties_match_method():
    u = UserFactory()
    sub = Subscription.objects.create(
        user=u, plan="starter",
        usage_seats=2, usage_storage_gb=5, usage_api_calls=10000,
    )
    assert sub.usage_percent_seats == sub.usage_percent("seats")
    assert sub.usage_percent_storage_gb == sub.usage_percent("storage_gb")
    assert sub.usage_percent_api_calls == sub.usage_percent("api_calls")
