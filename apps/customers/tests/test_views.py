import pytest

from apps.accounts.tests.factories import UserFactory
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def _staff(client):
    from django.utils import timezone
    u = UserFactory(is_staff=True)
    u.email_verified_at = timezone.now()
    u.save()
    client.force_login(u)
    return u


def _non_staff(client):
    from django.utils import timezone
    u = UserFactory(is_staff=False)
    u.email_verified_at = timezone.now()
    u.save()
    client.force_login(u)
    return u


def test_list_requires_login(client):
    response = client.get("/customers/")
    assert response.status_code == 302


def test_list_non_staff_forbidden(client):
    _non_staff(client)
    response = client.get("/customers/")
    assert response.status_code == 403


def test_list_staff_renders(client):
    _staff(client)
    CustomerFactory.create_batch(3)
    response = client.get("/customers/")
    assert response.status_code == 200
    assert b"New customer" in response.content


def test_list_hides_archived(client):
    _staff(client)
    active = CustomerFactory(name="Alice Active")
    archived = CustomerFactory(name="Bob Archived")
    archived.archive()
    response = client.get("/customers/")
    assert b"Alice Active" in response.content
    assert b"Bob Archived" not in response.content


def test_detail_staff_renders(client):
    _staff(client)
    c = CustomerFactory(name="Alice Chen", email="alice@example.com")
    response = client.get(f"/customers/{c.pk}/")
    assert response.status_code == 200
    assert b"Alice Chen" in response.content
    assert b"alice@example.com" in response.content


def test_detail_archived_returns_404(client):
    _staff(client)
    c = CustomerFactory()
    c.archive()
    response = client.get(f"/customers/{c.pk}/")
    assert response.status_code == 404


def test_create_post_valid(client):
    _staff(client)
    response = client.post("/customers/new/", {
        "name": "Alice Chen",
        "email": "alice@example.com",
        "phone": "", "company": "", "address": "", "city": "", "country": "",
        "status": "active", "notes": "",
    })
    assert response.status_code == 302
    assert Customer.objects.filter(email="alice@example.com").exists()


def test_update_persists_changes(client):
    _staff(client)
    c = CustomerFactory(name="Before", email="b@example.com")
    response = client.post(f"/customers/{c.pk}/edit/", {
        "name": "After",
        "email": "b@example.com",
        "phone": "", "company": "", "address": "", "city": "", "country": "",
        "status": "active", "notes": "",
    })
    assert response.status_code == 302
    c.refresh_from_db()
    assert c.name == "After"


def test_archive_soft_deletes(client):
    _staff(client)
    c = CustomerFactory()
    response = client.post(f"/customers/{c.pk}/archive/")
    assert response.status_code == 302
    c.refresh_from_db()
    assert c.deleted_at is not None


def test_archive_requires_staff(client):
    _non_staff(client)
    c = CustomerFactory()
    response = client.post(f"/customers/{c.pk}/archive/")
    assert response.status_code == 403
    c.refresh_from_db()
    assert c.deleted_at is None
