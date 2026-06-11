"""Per-user table preferences (column visibility) helpers.

Backed by the generic `UserPreference(user, key, value_json)` model in
apps.core.models. The key shape is `table.<table_key>.<setting>` so we
can grow other per-table prefs (page_size, density, etc.) without a
migration.
"""
from collections.abc import Iterable

VISIBLE_COLUMNS_SUFFIX = "visible_columns"


def _visible_columns_key(table_key: str) -> str:
    return f"table.{table_key}.{VISIBLE_COLUMNS_SUFFIX}"


def get_visible_columns(user, table_key: str) -> set[str] | None:
    """Return the set of column keys the user has chosen to show, or None
    if they haven't customized this table (callers should treat None as
    "show all non-hidden defaults").
    """
    if not getattr(user, "is_authenticated", False):
        return None
    from apps.core.models import UserPreference
    try:
        pref = UserPreference.objects.get(user=user, key=_visible_columns_key(table_key))
    except UserPreference.DoesNotExist:
        return None
    value = pref.value or {}
    cols = value.get("columns")
    return set(cols) if isinstance(cols, list) else None


def set_visible_columns(user, table_key: str, columns: Iterable[str]) -> None:
    """Persist the user's column visibility choice for `table_key`."""
    if not getattr(user, "is_authenticated", False):
        return
    from apps.core.models import UserPreference
    UserPreference.objects.update_or_create(
        user=user,
        key=_visible_columns_key(table_key),
        defaults={"value": {"columns": sorted(set(columns))}},
    )
