import pytest
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch

from apps.core.navigation import (
    NAV_ITEMS,
    NavItem,
    get_nav_groups,
    get_palette_entries,
    get_visible_items,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_nav_items_expose_expected_labels():
    # Labels are gettext_lazy proxies — force str() so set comparison is
    # locale-independent (translation state from other tests can leak).
    from django.utils.translation import override
    with override("en"):
        labels = {str(i.label) for i in NAV_ITEMS}
    assert labels == {
        "CRM", "Dashboard", "Lead", "Broker API",
        "Administration", "Users", "Settings", "Guida",
    }


def test_all_nav_items_have_resolvable_urls():
    # Ogni voce di menu deve puntare a una URL esistente.
    for item in NAV_ITEMS:
        assert item.resolved_url()


def test_anonymous_sees_only_public_items():
    labels = {str(i.label) for i in get_visible_items(None)}
    assert "Settings" in labels
    assert "Lead" not in labels          # requires_staff
    assert "Broker API" not in labels    # requires_admin


def test_staff_non_admin_excludes_admin_only_items():
    user = User.objects.create_user(username="staff1", password="pw", is_staff=True)
    labels = {str(i.label) for i in get_visible_items(user)}
    assert "Lead" in labels
    assert "Users" in labels
    assert "Broker API" not in labels      # solo Super Admin
    assert "Administration" not in labels   # solo Super Admin


def test_superuser_sees_admin_only_items():
    user = User.objects.create_user(username="admin1", password="pw",
                                    is_staff=True, is_superuser=True)
    labels = {str(i.label) for i in get_visible_items(user)}
    assert "Broker API" in labels
    assert "Administration" in labels


def test_role_admin_sees_admin_only_items():
    user = User.objects.create_user(username="roleadmin", password="pw",
                                    is_staff=True, role="admin")
    labels = {str(i.label) for i in get_visible_items(user)}
    assert "Broker API" in labels


def test_nav_groups_order_is_crm_then_account():
    user = User.objects.create_user(username="g1", password="pw",
                                    is_staff=True, is_superuser=True)
    groups = [g["label"] for g in get_nav_groups(user)]
    assert groups == ["CRM", "Account"]


def test_palette_entries_resolved_and_serializable():
    user = User.objects.create_user(username="p1", password="pw",
                                    is_staff=True, is_superuser=True)
    by_label = {e["label"]: e for e in get_palette_entries(user)}
    assert by_label["Lead"]["url"].startswith("/")
    assert isinstance(by_label["Lead"]["keywords"], list)
    assert by_label["Broker API"]["group"] == "CRM"


def test_nav_item_bad_url_raises_on_resolution():
    bad = NavItem(label="Bad", url_name="does_not_exist", icon="x")
    with pytest.raises(NoReverseMatch):
        bad.resolved_url()
