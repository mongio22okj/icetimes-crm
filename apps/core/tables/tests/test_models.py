"""Schema-level tests for UserPreference + SavedView."""
import pytest
from django.db import IntegrityError

from apps.accounts.tests.factories import UserFactory
from apps.core.models import SavedView, UserPreference

pytestmark = pytest.mark.django_db


def test_userpreference_uniqueness_per_user_per_key():
    user = UserFactory()
    UserPreference.objects.create(user=user, key="ui.density", value={"v": "compact"})
    with pytest.raises(IntegrityError):
        UserPreference.objects.create(user=user, key="ui.density", value={"v": "spacious"})


def test_userpreference_value_defaults_to_empty_dict():
    user = UserFactory()
    pref = UserPreference.objects.create(user=user, key="x.y")
    pref.refresh_from_db()
    assert pref.value == {}


def test_savedview_uniqueness_per_user_per_table_per_name():
    user = UserFactory()
    SavedView.objects.create(user=user, table_key="customers", name="VIPs")
    with pytest.raises(IntegrityError):
        SavedView.objects.create(user=user, table_key="customers", name="VIPs")


def test_savedview_same_name_in_different_table_is_ok():
    user = UserFactory()
    SavedView.objects.create(user=user, table_key="customers", name="Recent")
    SavedView.objects.create(user=user, table_key="orders", name="Recent")
    assert SavedView.objects.filter(user=user, name="Recent").count() == 2


def test_savedview_default_ordering_groups_by_table_then_name():
    user = UserFactory()
    SavedView.objects.create(user=user, table_key="orders", name="B")
    SavedView.objects.create(user=user, table_key="customers", name="A")
    SavedView.objects.create(user=user, table_key="orders", name="A")
    names = list(SavedView.objects.values_list("table_key", "name"))
    assert names == [("customers", "A"), ("orders", "A"), ("orders", "B")]
