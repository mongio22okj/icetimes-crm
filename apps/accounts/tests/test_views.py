import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from .factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
def test_register_get_renders_form(client):
    response = client.get(reverse("register"))
    assert response.status_code == 200
    assert b"Create your account" in response.content


@pytest.mark.django_db
def test_register_post_creates_user_and_redirects(client):
    response = client.post(reverse("register"), {
        "username": "newuser",
        "email": "new@example.com",
        "first_name": "New",
        "last_name": "User",
        "password1": "Complex-passw0rd",
        "password2": "Complex-passw0rd",
    })
    assert response.status_code == 302
    assert User.objects.filter(username="newuser").exists()


@pytest.mark.django_db
def test_register_post_auto_logs_in(client):
    client.post(reverse("register"), {
        "username": "autoin",
        "email": "a@b.com",
        "first_name": "Auto",
        "last_name": "In",
        "password1": "Complex-passw0rd",
        "password2": "Complex-passw0rd",
    })
    # After registration, the session must carry the auth hash
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_factory_user_can_authenticate(client):
    user = UserFactory(username="alice")
    assert client.login(username="alice", password="password")
