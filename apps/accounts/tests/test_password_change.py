import pytest

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_password_change_requires_login(client):
    response = client.get("/settings/password/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_password_change_renders_form_fields(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/password/")
    assert response.status_code == 200
    assert b"Current password" in response.content
    assert b"New password" in response.content


def test_password_change_success_keeps_user_logged_in(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    assert client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "oldpass1234",
            "new_password1": "newpass-x9!",
            "new_password2": "newpass-x9!",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert response.context["user"].is_authenticated
    user.refresh_from_db()
    assert user.check_password("newpass-x9!")


def test_password_change_rejects_wrong_old_password(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "WRONG",
            "new_password1": "newpass-x9!",
            "new_password2": "newpass-x9!",
        },
    )
    assert response.status_code == 200
    assert b"Your old password was entered incorrectly" in response.content
    user.refresh_from_db()
    assert user.check_password("oldpass1234"), "password should be unchanged"


def test_password_change_rejects_mismatched_confirmation(client):
    user = UserFactory()
    user.set_password("oldpass1234")
    user.save()
    client.login(username=user.username, password="oldpass1234")

    response = client.post(
        "/settings/password/",
        {
            "old_password": "oldpass1234",
            "new_password1": "newpass-x9!",
            "new_password2": "different",
        },
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("oldpass1234"), "password should be unchanged"
