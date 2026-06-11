"""Query-param → ORM filter + sort translation.

Filter values come from request.GET. The naming convention:

    ?<column_key>=<value>           — text, select, boolean, numeric (single)
    ?<column_key>=<a>&<column_key>=<b>  — multi-select (repeated key)
    ?<column_key>__from=<lo>&<column_key>__to=<hi>  — daterange / numeric range
    ?q=<text>                       — global search across `searchable=True` columns
    ?sort=<col>                     — ascending sort
    ?sort=-<col>                    — descending sort
    ?sort=<a>,-<b>                  — multi-sort (left-to-right priority)

ORM lookup notes:
- Column keys can use Django ORM dot syntax in TableConfig (e.g. "owner.email")
  but ORM filters use double-underscore. We translate "." → "__" for filtering.
- `boolean` accepts "1"/"true"/"on" → True, "0"/"false"/"" → False, anything else
  → ignored (no filter applied). Keeps clean URLs working.
- `daterange` accepts ISO dates ("2026-04-01"). Invalid dates → silently ignored
  (the goal is robustness against URL fiddling, not error reporting).

Anything that doesn't match a known column with a configured filter is
ignored — protects against URL injection of unfiltered fields.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Q, QuerySet

from apps.core.tables.config import Column, Filter, TableConfig


def _orm_path(key: str) -> str:
    return key.replace(".", "__")


def _coerce_bool(raw: str) -> bool | None:
    s = (raw or "").strip().lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return None


def _coerce_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _coerce_number(raw: str) -> float | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _filter_q(col: Column, params) -> Q | None:
    """Translate a single column's filter value(s) to a Q, or None if no filter."""
    f: Filter = col.filter  # type: ignore[assignment]
    path = _orm_path(col.key)
    if f.kind == "text":
        v = params.get(col.key, "").strip()
        return Q(**{f"{path}__icontains": v}) if v else None
    if f.kind == "select":
        v = params.get(col.key, "").strip()
        return Q(**{path: v}) if v else None
    if f.kind == "multi":
        values = [v for v in params.getlist(col.key) if v]
        return Q(**{f"{path}__in": values}) if values else None
    if f.kind == "boolean":
        b = _coerce_bool(params.get(col.key, ""))
        return Q(**{path: b}) if b is not None else None
    if f.kind == "numeric":
        lo = _coerce_number(params.get(f"{col.key}__from", ""))
        hi = _coerce_number(params.get(f"{col.key}__to", ""))
        # Single-value form ?key=N is also accepted for convenience.
        eq = _coerce_number(params.get(col.key, ""))
        if lo is not None or hi is not None:
            q = Q()
            if lo is not None:
                q &= Q(**{f"{path}__gte": lo})
            if hi is not None:
                q &= Q(**{f"{path}__lte": hi})
            return q
        return Q(**{path: eq}) if eq is not None else None
    if f.kind == "daterange":
        lo = _coerce_date(params.get(f"{col.key}__from", ""))
        hi = _coerce_date(params.get(f"{col.key}__to", ""))
        if lo is None and hi is None:
            return None
        q = Q()
        if lo is not None:
            q &= Q(**{f"{path}__gte": lo})
        if hi is not None:
            q &= Q(**{f"{path}__lte": hi})
        return q
    return None


def apply_filters(qs: QuerySet, params, config: TableConfig) -> QuerySet:
    """Apply per-column filters + global search."""
    # Per-column filters
    combined = Q()
    any_applied = False
    for col in config.columns:
        if col.filter is None:
            continue
        q = _filter_q(col, params)
        if q is not None:
            combined &= q
            any_applied = True
    if any_applied:
        qs = qs.filter(combined)

    # Global search
    q_text = params.get("q", "").strip()
    if q_text:
        searchable = [_orm_path(c.key) for c in config.columns if c.searchable]
        if searchable:
            search_q = Q()
            for path in searchable:
                search_q |= Q(**{f"{path}__icontains": q_text})
            qs = qs.filter(search_q)
    return qs


def parse_sort_param(raw: str | None, allowed: set[str]) -> list[str]:
    """Parse `?sort=` into a list of ORM order_by terms.

    - Accepts comma-separated multi-sort (left = primary).
    - Strips leading "-" to check the column is allowed, re-applies it.
    - Silently drops any term whose column isn't in `allowed`. Empty result
      means "no sort applied — caller falls back to default_sort".
    - Returns ORM-style paths (dots → underscores).
    """
    if not raw:
        return []
    out: list[str] = []
    for raw_term in raw.split(","):
        term = raw_term.strip()
        if not term:
            continue
        desc = term.startswith("-")
        col = term.lstrip("-")
        if col not in allowed:
            continue
        path = _orm_path(col)
        out.append(f"-{path}" if desc else path)
    return out


def apply_sort(qs: QuerySet, params, config: TableConfig) -> QuerySet:
    """Apply ordering from `?sort=…`, falling back to `config.default_sort`."""
    sort_terms = parse_sort_param(params.get("sort"), config.sortable_column_keys())
    if sort_terms:
        return qs.order_by(*sort_terms)
    return qs.order_by(config.default_sort)
