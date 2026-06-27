import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


def _staff_request(path="/"):
    request = RequestFactory().get(path)
    request.user = get_user_model()(username="navtest", is_staff=True,
                                    is_superuser=True)
    return request


def test_active_exact_only_matches_same_path():
    from apps.core.templatetags.apex import active
    assert active("/", "/", exact=True) == "bg-sidebar-accent text-sidebar-accent-foreground"
    assert active("/orders/", "/", exact=True) == ""


def test_navigation_context_has_crm_group_with_lead():
    from apps.core.context_processors import navigation

    ctx = navigation(_staff_request())
    crm = next(g for g in ctx["nav_groups"] if g["label"] == "CRM")
    labels = {i["label"] for i in crm["items"]}
    assert "Lead" in labels
    assert "Dashboard" in labels


def test_navigation_context_nav_items_json_is_list():
    from apps.core.context_processors import navigation

    request = RequestFactory().get("/")
    request.user = get_user_model()(username="anon", is_staff=False)
    ctx = navigation(request)
    payload = ctx["nav_items_json"]
    assert isinstance(payload, list)
    # un non-staff non deve vedere voci staff-only come "Users"
    assert all(e["label"] != "Users" for e in payload)


def test_sidebar_renders_via_dashboard_layout():
    from django.template.loader import render_to_string

    user = get_user_model().objects.create_user(
        username="sidebar", password="pw", is_staff=True, is_superuser=True)
    request = RequestFactory().get("/")
    request.user = user
    html = render_to_string("layouts/dashboard.html", {}, request=request)
    assert "CRM" in html          # gruppo CRM
    assert "Lead" in html         # voce Lead
    assert "w-[260px]" in html
    assert 'aria-hidden="true"' in html, "SVG icons must be aria-hidden"
    assert 'viewBox="0 0 24 24"' in html, "Icon SVG must render"
