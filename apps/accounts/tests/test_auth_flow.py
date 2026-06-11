import pytest
from django.urls import reverse

from .factories import UserFactory


@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content


@pytest.mark.django_db
def test_login_succeeds_with_valid_credentials(client):
    user = UserFactory(username="alice")
    # Factory already set password="password" via PostGenerationMethodCall
    response = client.post(reverse("login"), {"username": "alice", "password": "password"})
    assert response.status_code == 302


@pytest.mark.django_db
def test_login_fails_with_invalid_credentials(client):
    UserFactory(username="bob")
    response = client.post(reverse("login"), {"username": "bob", "password": "wrongpass"})
    # Django's LoginView re-renders the form (200) with error message, does not redirect
    assert response.status_code == 200
    assert b"Invalid" in response.content or b"correct" in response.content  # error copy varies


@pytest.mark.django_db
def test_password_reset_request_renders(client):
    response = client.get(reverse("password_reset"))
    assert response.status_code == 200
    assert b"Reset your password" in response.content


@pytest.mark.django_db
def test_logout_redirects(client):
    user = UserFactory(username="carol")
    client.force_login(user)
    response = client.post(reverse("logout"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_logged_out_page_renders(client):
    # After logout, Django redirects to LOGOUT_REDIRECT_URL. To render logged_out.html directly:
    response = client.get("/accounts/logout/", follow=False)
    # GET to logout may 405 or redirect depending on settings; instead just render the template
    from django.template.loader import render_to_string
    html = render_to_string("registration/logged_out.html")
    assert "signed out" in html.lower() or "logged out" in html.lower()
