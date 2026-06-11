import pytest

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_appearance_requires_login(client):
    response = client.get("/settings/appearance/")
    assert response.status_code == 302


def test_appearance_renders_three_options(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/settings/appearance/")
    assert response.status_code == 200
    assert b"Light" in response.content
    assert b"Dark" in response.content
    assert b"System" in response.content
