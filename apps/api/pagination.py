"""Cursor pagination helper for list endpoints.

`?cursor=<id>&limit=N` returns rows with `id < cursor` (descending),
plus a `next_cursor` for the next page.

Why cursor instead of ?page=N: page-numbered pagination races with
inserts (a new row at the top can shift everything down a page);
cursors don't. The dashboard list pages use page numbers because
they're better UX in a browser; the API uses cursors because it's
better for machine consumers.
"""
from __future__ import annotations

from django.db.models import QuerySet

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def parse_limit(raw: str | int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, n))


def paginate(qs: QuerySet, *, cursor: str | None, limit: int | str | None,
             order_by: str = "-id"):
    """Paginate a queryset by id (default ordering -id).

    Returns ({"items": [...], "next_cursor": "...", "total": N}-shaped dict).
    The caller is responsible for materializing items into Pydantic schemas.
    """
    n = parse_limit(limit)
    total = qs.count()
    sliced = qs.order_by(order_by)
    if cursor:
        try:
            cursor_id = int(cursor)
            if order_by.startswith("-"):
                sliced = sliced.filter(id__lt=cursor_id)
            else:
                sliced = sliced.filter(id__gt=cursor_id)
        except (TypeError, ValueError):
            pass
    rows = list(sliced[:n + 1])
    next_cursor = None
    if len(rows) > n:
        next_cursor = str(rows[n - 1].id)
        rows = rows[:n]
    return {"items": rows, "next_cursor": next_cursor, "total": total}
