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
    # Labels are gettext_lazy proxies — force str() so set comparison
    # is locale-independent (translation activate state from other tests
    # would otherwise affect resolution).
    from django.utils.translation import override
    with override("en"):
        labels = {str(i.label) for i in NAV_ITEMS}
    assert labels == {"Overview", "Analytics", "CRM", "eCommerce", "SaaS", "Orders", "Customers", "Invoices", "Mail", "Chat", "Calendar", "Kanban", "Projects", "Team", "Activity", "Files", "Realtime", "Landings", "Pricing", "Support", "Help center", "Blog", "Onboarding", "Components", "Charts", "Coming Soon", "Maintenance", "503 Page", "Forms", "Widgets", "Datatable", "API docs", "Maps", "Products", "Administration", "Users", "Settings", "Billing", "Organizations"}


def test_get_visible_items_filters_staff_only_for_non_staff():
    user = User.objects.create_user(username="regular", password="pw", is_staff=False)
    items = get_visible_items(user)
    assert "Users" not in {i.label for i in items}
    assert "Overview" in {i.label for i in items}


def test_get_visible_items_includes_staff_only_for_staff():
    user = User.objects.create_user(username="admin", password="pw", is_staff=True)
    items = get_visible_items(user)
    assert "Users" in {i.label for i in items}


def test_palette_entries_have_resolved_urls():
    user = User.objects.create_user(username="admin", password="pw", is_staff=True)
    entries = get_palette_entries(user)
    by_label = {e["label"]: e for e in entries}
    assert by_label["Overview"]["url"] == "/"
    assert by_label["Orders"]["url"] == "/orders/"
    assert by_label["Customers"]["url"] == "/customers/"
    assert by_label["Settings"]["url"] == "/settings/profile/"
    assert "home" in by_label["Overview"]["keywords"]


def test_nav_item_bad_url_raises_on_resolution():
    bad = NavItem(label="Bad", url_name="does_not_exist", icon="x")
    with pytest.raises(NoReverseMatch):
        bad.resolved_url()


def test_get_nav_groups_preserves_overview_commerce_apps_account_order():
    user = User.objects.create_user(username="ordertest", password="pw", is_staff=True)
    groups = get_nav_groups(user)
    assert [g["label"] for g in groups] == ["Dashboards", "Commerce", "Apps", "Marketing", "Showcase", "Account"]


def test_customers_in_palette_only_for_staff():
    from apps.accounts.tests.factories import UserFactory
    from apps.core.navigation import get_palette_entries

    staff = UserFactory(is_staff=True)
    non_staff = UserFactory(is_staff=False)
    staff_labels = {e["label"] for e in get_palette_entries(staff)}
    non_staff_labels = {e["label"] for e in get_palette_entries(non_staff)}
    assert "Customers" in staff_labels
    assert "Customers" not in non_staff_labels
