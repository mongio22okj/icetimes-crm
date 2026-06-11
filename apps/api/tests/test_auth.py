"""APIKey storage + KeyAuth + management command tests."""
import pytest
from django.core.management import call_command

from apps.accounts.tests.factories import UserFactory
from apps.api.models import KEY_BRAND, APIKey

pytestmark = pytest.mark.django_db


# ── APIKey model ──────────────────────────────────────────────────────


def test_generate_returns_raw_with_brand_prefix():
    user = UserFactory()
    instance, raw = APIKey.generate(user, "test")
    assert raw.startswith(f"{KEY_BRAND}_")
    assert instance.key_prefix in raw
    assert len(raw) > 20


def test_raw_key_is_not_stored_in_database():
    user = UserFactory()
    _, raw = APIKey.generate(user, "test")
    # The raw key shouldn't appear in any field of the saved row.
    instance = APIKey.objects.get(user=user)
    assert raw != instance.key_hash
    assert raw not in instance.key_hash
    assert instance.key_hash != ""
    assert len(instance.key_hash) == 64  # SHA-256 hex


def test_lookup_finds_active_key():
    user = UserFactory()
    instance, raw = APIKey.generate(user, "test")
    found = APIKey.lookup(raw)
    assert found is not None
    assert found.pk == instance.pk


def test_lookup_returns_none_for_unknown_key():
    assert APIKey.lookup("apex_doesnotexist") is None


def test_lookup_returns_none_for_revoked_key():
    user = UserFactory()
    instance, raw = APIKey.generate(user, "test")
    instance.revoke()
    assert APIKey.lookup(raw) is None


def test_lookup_returns_none_for_expired_key():
    from datetime import timedelta

    from django.utils import timezone
    user = UserFactory()
    instance, raw = APIKey.generate(user, "test", expires_at=timezone.now() - timedelta(seconds=1))
    assert APIKey.lookup(raw) is None


def test_lookup_returns_none_for_malformed_string():
    assert APIKey.lookup("") is None
    assert APIKey.lookup("not-a-key") is None


def test_touch_updates_last_used_at():
    user = UserFactory()
    instance, raw = APIKey.generate(user, "test")
    assert instance.last_used_at is None
    instance.touch()
    instance.refresh_from_db()
    assert instance.last_used_at is not None


def test_two_keys_for_same_user_have_different_hashes():
    user = UserFactory()
    _, raw1 = APIKey.generate(user, "k1")
    _, raw2 = APIKey.generate(user, "k2")
    assert raw1 != raw2


# ── Endpoint auth ─────────────────────────────────────────────────────


def test_endpoint_requires_authorization_header(client):
    r = client.get("/api/v1/customers/")
    assert r.status_code == 401


def test_endpoint_rejects_unknown_token(client):
    r = client.get("/api/v1/customers/",
                   HTTP_AUTHORIZATION="Bearer apex_unknown")
    assert r.status_code == 401


def test_endpoint_accepts_valid_token(client, auth_headers):
    r = client.get("/api/v1/customers/", **auth_headers)
    assert r.status_code == 200


def test_endpoint_touch_updates_last_used(client, auth_headers, api_key):
    assert api_key["instance"].last_used_at is None
    client.get("/api/v1/customers/", **auth_headers)
    api_key["instance"].refresh_from_db()
    assert api_key["instance"].last_used_at is not None


def test_endpoint_rejects_revoked_token_after_revoke(client, api_key):
    api_key["instance"].revoke()
    r = client.get("/api/v1/customers/",
                   HTTP_AUTHORIZATION=f"Bearer {api_key['raw']}")
    assert r.status_code == 401


# ── Management command ────────────────────────────────────────────────


def test_create_api_key_command_creates_key(capsys):
    user = UserFactory(username="apicli")
    call_command("create_api_key", "apicli", name="from-cli")
    captured = capsys.readouterr().out
    assert "Created APIKey" in captured
    assert "apex_" in captured
    assert APIKey.objects.filter(user=user, name="from-cli").exists()


def test_create_api_key_command_unknown_user_errors():
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command("create_api_key", "nope_no_user")
