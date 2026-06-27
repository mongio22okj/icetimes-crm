import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.views.generic import TemplateView

from apps.core.breadcrumbs import BreadcrumbsMixin

pytestmark = pytest.mark.django_db


def _dispatch(view_cls, path="/"):
    view = view_cls()
    view.request = RequestFactory().get(path)
    return view


def test_single_level_breadcrumb_includes_dashboard_root_and_current():
    class OrdersListView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Orders"

    view = _dispatch(OrdersListView, "/orders/")
    crumbs = view.get_breadcrumbs()
    assert crumbs == [("Dashboard", "/"), ("Orders", None)]


def test_nested_breadcrumb_walks_parent():
    # Il label del parent è risolto da NAV_ITEMS (tracking:lead_list -> "Lead").
    class LeadEditView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Edit lead"
        breadcrumb_parent = "tracking:lead_list"

    view = _dispatch(LeadEditView, "/tracking/5/edit/")
    crumbs = view.get_breadcrumbs()
    assert crumbs == [
        ("Dashboard", "/"),
        ("Lead", "/tracking/"),
        ("Edit lead", None),
    ]


def test_get_context_data_injects_breadcrumbs():
    class OrdersListView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Orders"

    view = _dispatch(OrdersListView)
    ctx = view.get_context_data()
    assert ctx["breadcrumbs"][0] == ("Dashboard", "/")
    assert ctx["breadcrumbs"][-1] == ("Orders", None)


def test_dynamic_title_via_override():
    class OrderDetailView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_parent = "orders:list"

        def get_breadcrumb_title(self):
            return "ORD-00042"

    view = _dispatch(OrderDetailView)
    crumbs = view.get_breadcrumbs()
    assert crumbs[-1] == ("ORD-00042", None)


def test_breadcrumbs_tag_renders_nothing_for_single_crumb():
    html = render_to_string("partials/breadcrumbs.html", {"crumbs": []})
    assert "<nav" not in html


def test_breadcrumbs_tag_renders_all_crumbs():
    html = render_to_string("partials/breadcrumbs.html", {
        "crumbs": [("Dashboard", "/"), ("Orders", "/orders/"), ("ORD-5", None)],
    })
    assert "Dashboard" in html and "/orders/" in html
    assert 'aria-current="page"' in html
    assert "ORD-5" in html
