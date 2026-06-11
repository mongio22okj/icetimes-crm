"""UserPreference + column-visibility helper tests."""
import pytest

from apps.accounts.tests.factories import UserFactory
from apps.core.models import UserPreference
from apps.core.tables.prefs import get_visible_columns, set_visible_columns

pytestmark = pytest.mark.django_db


def test_get_visible_columns_returns_none_for_unknown_table():
    user = UserFactory()
    assert get_visible_columns(user, "customers") is None


def test_get_visible_columns_returns_none_for_anonymous():
    """Anonymous users should not blow up; treat as "no preference saved"."""
    from django.contrib.auth.models import AnonymousUser
    assert get_visible_columns(AnonymousUser(), "customers") is None


def test_set_visible_columns_creates_then_get_returns_set():
    user = UserFactory()
    set_visible_columns(user, "customers", ["name", "email", "status"])
    assert get_visible_columns(user, "customers") == {"name", "email", "status"}


def test_set_visible_columns_updates_existing_pref():
    user = UserFactory()
    set_visible_columns(user, "customers", ["name", "email"])
    set_visible_columns(user, "customers", ["name", "status"])
    assert get_visible_columns(user, "customers") == {"name", "status"}
    # Only one row per (user, key)
    assert UserPreference.objects.filter(
        user=user, key="table.customers.visible_columns"
    ).count() == 1


def test_set_visible_columns_dedupes_and_sorts_list_in_storage():
    user = UserFactory()
    set_visible_columns(user, "customers", ["b", "a", "b", "a"])
    pref = UserPreference.objects.get(user=user, key="table.customers.visible_columns")
    assert pref.value == {"columns": ["a", "b"]}


def test_two_tables_have_independent_prefs():
    user = UserFactory()
    set_visible_columns(user, "customers", ["name"])
    set_visible_columns(user, "orders", ["id", "total"])
    assert get_visible_columns(user, "customers") == {"name"}
    assert get_visible_columns(user, "orders") == {"id", "total"}


def test_two_users_have_independent_prefs():
    a = UserFactory()
    b = UserFactory()
    set_visible_columns(a, "customers", ["name"])
    assert get_visible_columns(b, "customers") is None
