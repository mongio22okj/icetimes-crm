import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name,headline_substr", [
    ("marketing:analytics", b"Decisions backed by data"),
    ("marketing:saas",      b"Ship features"),
    ("marketing:crm",       b"Every conversation"),
    ("marketing:ecommerce", b"From cart to fulfillment"),
])
def test_variant_anonymous_returns_200_with_headline(client, name, headline_substr):
    r = client.get(reverse(name))
    assert r.status_code == 200
    assert headline_substr in r.content


@pytest.mark.parametrize("name", [
    "marketing:hub",
    "marketing:analytics",
    "marketing:saas",
    "marketing:crm",
    "marketing:ecommerce",
])
def test_authenticated_user_can_access(client, name):
    user = UserFactory(is_staff=True)
    client.force_login(user)
    r = client.get(reverse(name))
    assert r.status_code == 200


def test_hub_links_to_all_variants(client):
    r = client.get(reverse("marketing:hub"))
    assert r.status_code == 200
    for name in ("analytics", "saas", "crm", "ecommerce"):
        url = reverse(f"marketing:{name}")
        assert url.encode() in r.content


# ----- Pricing -----

def test_pricing_anonymous_200_with_tiers(client):
    r = client.get(reverse("marketing:pricing"))
    assert r.status_code == 200
    for tier in (b"Starter", b"Pro", b"Enterprise"):
        assert tier in r.content


def test_pricing_shows_faq(client):
    r = client.get(reverse("marketing:pricing"))
    assert b"Frequently asked" in r.content


# ----- Support -----

def test_support_get_returns_form(client):
    r = client.get(reverse("marketing:support"))
    assert r.status_code == 200
    assert b"Contact us" in r.content or b"contact us" in r.content
    assert b'name="email"' in r.content


def test_support_post_creates_ticket(client):
    from apps.marketing.models import SupportTicket
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "subject": "Cannot log in",
        "body": "I forgot my password.",
    }
    r = client.post(reverse("marketing:support"), data=payload)
    assert r.status_code == 302
    ticket = SupportTicket.objects.get()
    assert ticket.email == "test@example.com"
    assert ticket.subject == "Cannot log in"


def test_support_post_invalid_email_renders_errors(client):
    from apps.marketing.models import SupportTicket
    payload = {
        "name": "Test",
        "email": "not-an-email",
        "subject": "Hi",
        "body": "test",
    }
    r = client.post(reverse("marketing:support"), data=payload)
    assert r.status_code == 200
    assert SupportTicket.objects.count() == 0
