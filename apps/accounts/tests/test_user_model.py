import pytest
from django.db import IntegrityError

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_email_stored_lowercased_on_save():
    u = User.objects.create_user(username="alice", email="Alice@Example.com", password="pw")
    u.refresh_from_db()
    assert u.email == "alice@example.com"


def test_duplicate_email_raises_at_db_level():
    User.objects.create_user(username="one", email="dup@example.com", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="two", email="dup@example.com", password="pw")


def test_case_insensitive_email_uniqueness():
    User.objects.create_user(username="one", email="alice@example.com", password="pw")
    with pytest.raises(IntegrityError):
        User.objects.create_user(username="two", email="Alice@EXAMPLE.com", password="pw")


def test_email_verified_at_defaults_to_none():
    u = User.objects.create_user(username="alice", email="alice@example.com", password="pw")
    assert u.email_verified_at is None
