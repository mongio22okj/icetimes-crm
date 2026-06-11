import pytest
from django.contrib.auth import get_user_model

from apps.accounts.tests.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
def test_user_list_requires_staff(client):
    # Non-staff user hits /users/ — expect 403
    client.force_login(UserFactory(is_staff=False))
    response = client.get("/users/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_user_list_anon_redirects_to_login(client):
    response = client.get("/users/")
    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_can_list_users(client):
    client.force_login(UserFactory(is_staff=True))
    UserFactory.create_batch(3)
    response = client.get("/users/")
    assert response.status_code == 200
    # Header text
    assert b"Users" in response.content


@pytest.mark.django_db
def test_staff_can_create_user(client):
    client.force_login(UserFactory(is_staff=True))
    response = client.post("/users/new/", {
        "username": "created",
        "email": "c@example.com",
        "first_name": "C",
        "last_name": "D",
        "role": "staff",
        "password1": "Complex-passw0rd-1",
        "password2": "Complex-passw0rd-1",
    })
    assert response.status_code == 302
    assert User.objects.filter(username="created").exists()


@pytest.mark.django_db
def test_non_staff_cannot_create_user(client):
    client.force_login(UserFactory(is_staff=False))
    response = client.post("/users/new/", {
        "username": "nope",
        "email": "n@example.com",
        "first_name": "N",
        "last_name": "O",
        "role": "staff",
        "password1": "Complex-passw0rd-1",
        "password2": "Complex-passw0rd-1",
    })
    assert response.status_code == 403
    assert not User.objects.filter(username="nope").exists()


@pytest.mark.django_db
def test_staff_can_update_user(client):
    staff = UserFactory(is_staff=True)
    target = UserFactory(first_name="Old")
    client.force_login(staff)
    response = client.post(f"/users/{target.pk}/edit/", {
        "username": target.username,
        "email": target.email,
        "first_name": "New",
        "last_name": target.last_name,
        "role": target.role,
        "bio": "Edited",
    })
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.first_name == "New"
    assert target.bio == "Edited"


@pytest.mark.django_db
def test_user_detail_renders_for_staff(client):
    staff = UserFactory(is_staff=True)
    target = UserFactory(username="viewme")
    client.force_login(staff)
    response = client.get(f"/users/{target.pk}/")
    assert response.status_code == 200
    assert b"viewme" in response.content
