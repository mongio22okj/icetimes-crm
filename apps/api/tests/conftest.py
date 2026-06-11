"""Shared fixtures for API tests."""
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.api.models import APIKey


@pytest.fixture
def user(db):
    return UserFactory(is_staff=True, is_active=True)


@pytest.fixture
def api_key(user):
    instance, raw = APIKey.generate(user, "test")
    return {"instance": instance, "raw": raw}


@pytest.fixture
def auth_headers(api_key):
    """Headers dict ready to spread into client.get(... **auth_headers)."""
    return {"HTTP_AUTHORIZATION": f"Bearer {api_key['raw']}"}
