"""Public configuration types for the datatable system.

These are intentionally plain dataclasses — frozen so a TableConfig
on a view class is safe to share across requests, and free of any view
or queryset logic so they're trivially testable.

The `TableView` mixin (apps.core.tables.views) reads these to drive
template rendering, query mutation, and bulk-action dispatch.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

# Filter widget kinds. Each maps to a small partial under
# templates/core/tables/_filter_<kind>.html and to a translator in
# apps.core.tables.filters that converts query params to ORM Q objects.
FilterKind = Literal["text", "select", "multi", "daterange", "numeric", "boolean"]
ColumnAlign = Literal["left", "right", "center"]
PaginationKind = Literal["page", "cursor"]
ExportFormat = Literal["csv", "xlsx", "pdf"]


@dataclass(frozen=True)
class Filter:
    """Per-column filter widget descriptor."""
    kind: FilterKind
    label: str | None = None
    # Choices for select/multi. Use a tuple of (value, label) pairs, or a
    # zero-arg callable that returns choices (for choices that depend on
    # request state — resolved at render time).
    choices: tuple | Callable[[], tuple] = ()
    placeholder: str = ""

    def resolved_choices(self) -> tuple:
        if callable(self.choices):
            return tuple(self.choices())
        return tuple(self.choices)


@dataclass(frozen=True)
class Column:
    """One table column.

    `key` is an ORM field path (e.g. "owner.email"), an annotated alias,
    or any attribute the row exposes. The view's queryset must be able
    to sort + filter on this key when those features are enabled.
    """
    key: str
    label: str
    sortable: bool = True
    searchable: bool = False
    filter: Filter | None = None
    align: ColumnAlign = "left"
    width: str | None = None              # CSS value, e.g. "8rem"
    priority: int = 1                     # 1 always · 2 hide<md · 3 hide<sm
    pinned: bool = False                  # cannot be hidden via visibility menu
    formatter: Callable | None = None     # value → str/SafeString
    template: str | None = None           # override: render via {% include %}


@dataclass(frozen=True)
class BulkAction:
    """One entry in the bulk-action toolbar."""
    slug: str
    label: str
    confirm_text: str | None = None       # shown in modal; None → no confirm
    icon: str = ""                        # lucide icon name
    destructive: bool = False             # styled red


@dataclass(frozen=True)
class TableConfig:
    """The full configuration for a TableView.

    `key` must be unique across the project — it scopes UserPreference
    rows (column visibility) and SavedView rows (named filter+sort combos).
    Convention: snake-case, matches the model name (e.g. "customers").
    """
    key: str
    columns: tuple[Column, ...]
    bulk_actions: tuple[BulkAction, ...] = ()
    default_sort: str = "-id"
    page_size: int = 25
    pagination: PaginationKind = "page"
    sticky_first: bool = False
    sticky_last: bool = False
    row_url: Callable | None = None       # row → detail URL (Enter / row click)
    exports: tuple[ExportFormat, ...] = ("csv", "xlsx", "pdf")
    # Filter UI placement: "drawer" (chips above + a Filters button opening
    # a side drawer, see Phase 11 spec open-question resolution) is the
    # default; "inline" puts each filter under its column header for compact
    # tables. Phase 11 ships "drawer" only; "inline" is reserved.
    filter_ui: Literal["drawer", "inline"] = "drawer"
    # Optional caption shown below the title — e.g. "1,248 customers".
    caption: str | None = None
    # Optional empty-state copy. Defaults are generic; set these for friendlier
    # zero-state messaging (e.g. "No customers yet" / "Add your first customer").
    empty_headline: str | None = None
    empty_body: str | None = None
    empty_icon: str = "inbox"
    # Allow the view to expose its bulk actions only when ≥ 1 row is
    # selected. Tables with no bulk actions skip the toolbar entirely.
    show_bulk_toolbar: bool = True
    # Reserved for Phase 11 follow-ups; kept here so `TableConfig(...)`
    # call sites don't need to change.
    extra: dict = field(default_factory=dict)

    def column_keys(self) -> tuple[str, ...]:
        return tuple(c.key for c in self.columns)

    def sortable_column_keys(self) -> set[str]:
        return {c.key for c in self.columns if c.sortable}

    def searchable_column_keys(self) -> set[str]:
        return {c.key for c in self.columns if c.searchable}

    def column(self, key: str) -> Column | None:
        for c in self.columns:
            if c.key == key:
                return c
        return None
