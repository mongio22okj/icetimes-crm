"""Filter + sort translation tests.

Use a small in-memory model — apps.customers.Customer — so we don't need
to spin up a separate test app. The Customer model has fields exercising
text, select, and daterange filters; we add a numeric filter via
`orders_count` annotation in `_qs()`.
"""
import pytest
from django.db.models import Count
from django.http import QueryDict

from apps.core.tables import Column, Filter, TableConfig
from apps.core.tables.filters import apply_filters, apply_sort, parse_sort_param
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def _config() -> TableConfig:
    return TableConfig(
        key="customers",
        columns=(
            Column("name", "Name", searchable=True),
            Column("email", "Email", searchable=True,
                   filter=Filter("text")),
            Column("status", "Status",
                   filter=Filter("select", choices=Customer.STATUS)),
            Column("created_at", "Created",
                   filter=Filter("daterange")),
            Column("orders_count", "Orders",
                   filter=Filter("numeric")),
            Column("notes", "Notes", sortable=False),
        ),
        default_sort="-id",
    )


def _qs():
    return Customer.objects.annotate(orders_count=Count("orders", distinct=True))


def _qd(d: dict) -> QueryDict:
    qd = QueryDict(mutable=True)
    for k, v in d.items():
        if isinstance(v, list):
            for item in v:
                qd.appendlist(k, item)
        else:
            qd[k] = v
    return qd


# ── apply_filters ────────────────────────────────────────────────────


def test_global_search_matches_searchable_columns():
    a = CustomerFactory(name="Aigars Acme", email="a@example.com")
    b = CustomerFactory(name="Beth Bright", email="b@example.com")
    qs = apply_filters(_qs(), _qd({"q": "acme"}), _config())
    assert set(qs.values_list("pk", flat=True)) == {a.pk}
    assert b.pk not in set(qs.values_list("pk", flat=True))


def test_text_filter_icontains():
    a = CustomerFactory(email="alice@northwind.example")
    b = CustomerFactory(email="bob@other.example")
    qs = apply_filters(_qs(), _qd({"email": "northwind"}), _config())
    assert set(qs.values_list("pk", flat=True)) == {a.pk}


def test_select_filter_exact_match():
    a = CustomerFactory(status="active")
    b = CustomerFactory(status="inactive")
    qs = apply_filters(_qs(), _qd({"status": "inactive"}), _config())
    assert set(qs.values_list("pk", flat=True)) == {b.pk}


def test_empty_filter_value_is_ignored():
    a = CustomerFactory(status="active")
    qs = apply_filters(_qs(), _qd({"status": ""}), _config())
    assert qs.count() == 1


def test_daterange_filter_clamps_both_ends():
    from datetime import datetime

    from django.utils.timezone import make_aware
    old = CustomerFactory()
    Customer.objects.filter(pk=old.pk).update(created_at=make_aware(datetime(2026, 1, 1)))
    new = CustomerFactory()
    Customer.objects.filter(pk=new.pk).update(created_at=make_aware(datetime(2026, 5, 1)))
    qs = apply_filters(_qs(),
                       _qd({"created_at__from": "2026-04-01", "created_at__to": "2026-12-31"}),
                       _config())
    pks = set(qs.values_list("pk", flat=True))
    assert pks == {new.pk}


def test_daterange_invalid_dates_are_silently_ignored():
    a = CustomerFactory()
    qs = apply_filters(_qs(),
                       _qd({"created_at__from": "not-a-date", "created_at__to": ""}),
                       _config())
    assert a.pk in set(qs.values_list("pk", flat=True))


def test_unknown_param_keys_are_ignored():
    a = CustomerFactory()
    # Random key with no matching column: no-op, no crash.
    qs = apply_filters(_qs(), _qd({"random_param": "evil"}), _config())
    assert a.pk in set(qs.values_list("pk", flat=True))


def test_unfiltered_column_is_not_filterable_via_url():
    """`notes` has no filter — `?notes=...` must NOT filter the queryset."""
    a = CustomerFactory(notes="public")
    b = CustomerFactory(notes="private")
    qs = apply_filters(_qs(), _qd({"notes": "private"}), _config())
    assert qs.count() == 2  # both rows still present


# ── apply_sort + parse_sort_param ───────────────────────────────────


def test_parse_sort_single_asc():
    assert parse_sort_param("name", {"name", "email"}) == ["name"]


def test_parse_sort_single_desc():
    assert parse_sort_param("-name", {"name"}) == ["-name"]


def test_parse_sort_multi():
    assert parse_sort_param("name,-email", {"name", "email"}) == ["name", "-email"]


def test_parse_sort_drops_disallowed():
    assert parse_sort_param("name,evil", {"name"}) == ["name"]


def test_parse_sort_translates_dots_to_underscores():
    assert parse_sort_param("owner.email", {"owner.email"}) == ["owner__email"]


def test_parse_sort_empty_returns_empty():
    assert parse_sort_param("", {"name"}) == []
    assert parse_sort_param(None, {"name"}) == []


def test_apply_sort_falls_back_to_default():
    a = CustomerFactory(name="A")
    b = CustomerFactory(name="B")
    qs = apply_sort(_qs(), _qd({}), _config())
    pks_in_order = list(qs.values_list("pk", flat=True))
    # default_sort = "-id" → newer first
    assert pks_in_order[0] == b.pk


def test_apply_sort_uses_query_param():
    a = CustomerFactory(name="A")
    b = CustomerFactory(name="B")
    qs = apply_sort(_qs(), _qd({"sort": "name"}), _config())
    assert list(qs.values_list("name", flat=True)) == ["A", "B"]


def test_apply_sort_ignores_disallowed_column_and_falls_back():
    """An unknown sort key falls back silently to default_sort."""
    a = CustomerFactory(name="A")
    b = CustomerFactory(name="B")
    qs = apply_sort(_qs(), _qd({"sort": "evil_field"}), _config())
    # falls back to -id → b first
    assert list(qs.values_list("pk", flat=True))[0] == b.pk
