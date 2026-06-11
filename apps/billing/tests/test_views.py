import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.billing.models import PaymentMethod, Subscription

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory()


# ── Auth ──────────────────────────────────────────────────────────────

def test_overview_redirects_anon(client):
    r = client.get(reverse("billing:overview"))
    assert r.status_code == 302


# ── Overview ──────────────────────────────────────────────────────────

def test_overview_lazily_creates_subscription(client, user):
    client.force_login(user)
    assert not Subscription.objects.filter(user=user).exists()
    r = client.get(reverse("billing:overview"))
    assert r.status_code == 200
    assert Subscription.objects.filter(user=user).exists()


def test_overview_renders_plan_card(client, user):
    client.force_login(user)
    r = client.get(reverse("billing:overview"))
    assert b"Current plan" in r.content
    assert b"Payment method" in r.content
    assert b"Recent invoices" in r.content


def test_overview_shows_usage_meters(client, user):
    client.force_login(user)
    r = client.get(reverse("billing:overview"))
    assert b"Seats" in r.content
    assert b"Storage" in r.content
    assert b"API calls" in r.content


# ── Plans ─────────────────────────────────────────────────────────────

def test_plans_lists_all_four_tiers(client, user):
    client.force_login(user)
    r = client.get(reverse("billing:plans"))
    assert b"Free" in r.content
    assert b"Starter" in r.content
    assert b"Pro" in r.content
    assert b"Enterprise" in r.content


def test_plans_cycle_toggle(client, user):
    client.force_login(user)
    r = client.get(reverse("billing:plans") + "?cycle=annual")
    assert r.context["cycle"] == "annual"


def test_change_plan_updates_subscription(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))  # ensure sub exists
    r = client.post(reverse("billing:change_plan"),
                    data={"plan": "pro", "cycle": "annual"})
    assert r.status_code == 302
    sub = Subscription.objects.get(user=user)
    assert sub.plan == "pro"
    assert sub.billing_cycle == "annual"
    assert sub.amount > 0


def test_change_plan_rejects_unknown_plan(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    r = client.post(reverse("billing:change_plan"),
                    data={"plan": "unknown", "cycle": "monthly"})
    assert r.status_code == 404


# ── Payment methods ────────────────────────────────────────────────────

def test_add_payment_method(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    r = client.post(reverse("billing:payment_methods"), data={
        "brand": "visa", "last4": "4242",
        "exp_month": "12", "exp_year": "2030",
        "cardholder": "Test User", "is_default": "on",
    })
    assert r.status_code == 302
    assert PaymentMethod.objects.filter(last4="4242").exists()


def test_add_payment_method_validates_last4(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    r = client.post(reverse("billing:payment_methods"), data={
        "brand": "visa", "last4": "abc",
        "exp_month": "12", "exp_year": "2030",
    })
    assert r.status_code == 200
    assert b"Enter the last 4" in r.content


def test_set_default_payment_method(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    sub = Subscription.objects.get(user=user)
    a = PaymentMethod.objects.create(subscription=sub, brand="visa", last4="1111",
                                     exp_month=1, exp_year=2030, is_default=True)
    b = PaymentMethod.objects.create(subscription=sub, brand="amex", last4="2222",
                                     exp_month=1, exp_year=2030, is_default=False)
    r = client.post(reverse("billing:set_default_pm", args=[b.pk]))
    assert r.status_code == 302
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.is_default is False
    assert b.is_default is True


def test_delete_payment_method(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    sub = Subscription.objects.get(user=user)
    pm = PaymentMethod.objects.create(subscription=sub, brand="visa", last4="9999",
                                      exp_month=1, exp_year=2030)
    r = client.post(reverse("billing:delete_pm", args=[pm.pk]))
    assert r.status_code == 302
    assert not PaymentMethod.objects.filter(pk=pm.pk).exists()


def test_cannot_delete_other_users_pm(client, user):
    other = UserFactory()
    other_sub = Subscription.objects.create(user=other, plan="pro")
    other_pm = PaymentMethod.objects.create(subscription=other_sub, brand="visa",
                                            last4="0000", exp_month=1, exp_year=2030)
    client.force_login(user)
    r = client.post(reverse("billing:delete_pm", args=[other_pm.pk]))
    assert r.status_code == 404
    assert PaymentMethod.objects.filter(pk=other_pm.pk).exists()


# ── Cancel / reactivate ────────────────────────────────────────────────

def test_cancel_view_renders(client, user):
    client.force_login(user)
    r = client.get(reverse("billing:cancel"))
    assert r.status_code == 200
    assert b"Cancel subscription" in r.content


def test_cancel_post_marks_subscription_canceled(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    r = client.post(reverse("billing:cancel"))
    assert r.status_code == 302
    sub = Subscription.objects.get(user=user)
    assert sub.is_canceled


def test_cancel_post_on_canceled_reactivates(client, user):
    client.force_login(user)
    client.get(reverse("billing:overview"))
    sub = Subscription.objects.get(user=user)
    sub.cancel()
    client.post(reverse("billing:cancel"))
    sub.refresh_from_db()
    assert not sub.is_canceled
