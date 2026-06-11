from django.test import RequestFactory


def test_navigation_context_has_dashboards_group():
    from apps.core.context_processors import navigation

    request = RequestFactory().get("/")
    ctx = navigation(request)
    groups = ctx["nav_groups"]
    dashboards = next(g for g in groups if g["label"] == "Dashboards")
    assert any(i["href"] == "/" and i["label"] == "Overview" for i in dashboards["items"])


def test_navigation_includes_products_and_orders_in_commerce():
    from apps.core.context_processors import navigation

    ctx = navigation(RequestFactory().get("/"))
    commerce = next(g for g in ctx["nav_groups"] if g["label"] == "Commerce")
    labels = {i["label"] for i in commerce["items"]}
    assert {"Orders", "Products"} <= labels


def test_active_exact_only_matches_same_path():
    from apps.core.templatetags.apex import active
    assert active("/", "/", exact=True) == "bg-sidebar-accent text-sidebar-accent-foreground"
    assert active("/orders/", "/", exact=True) == ""


def test_sidebar_renders_via_dashboard_layout():
    from django.template.loader import render_to_string

    html = render_to_string("layouts/dashboard.html", {}, request=RequestFactory().get("/"))
    assert "Dashboards" in html  # group label
    assert "Overview" in html    # dashboard entry
    assert "Orders" in html
    assert "Products" in html
    assert "w-[260px]" in html
    assert 'aria-hidden="true"' in html, "SVG icons must be aria-hidden"
    assert 'viewBox="0 0 24 24"' in html, "Icon SVG must render"


def test_navigation_exposes_nav_items_json_list():
    from django.contrib.auth import get_user_model

    from apps.core.context_processors import navigation

    user = get_user_model()(username="anon")
    user.is_staff = False
    request = RequestFactory().get("/")
    request.user = user
    ctx = navigation(request)
    payload = ctx["nav_items_json"]
    assert isinstance(payload, list)
    assert any(e["label"] == "Overview" and e["url"] == "/" for e in payload)
    assert all(e["label"] != "Users" for e in payload), "non-staff should not see Users"
