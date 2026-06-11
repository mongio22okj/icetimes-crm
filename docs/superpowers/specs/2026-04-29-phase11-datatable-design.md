# Phase 11 — HTMX Datatable

**Date:** 2026-04-29
**Status:** Draft
**Scope:** A reusable, server-driven datatable that any list view can opt into. Replaces the static `pages/datatable.html` demo with a real one, then upgrades Customers / Orders / Invoices / Products / Users / Activity. Tables are where buyers stress-test dashboards — this phase makes ours top-tier without turning the stack into a SPA.

## Context

Per [phases 10–19 roadmap](2026-04-29-phase10-19-roadmap.md#phase-11--htmx-datatable) — the existing list views render a single static page. No sort, no filter, no bulk actions, no exports. Premium kits ship grids with column visibility, saved views, sticky headers, server-side everything. We can match that without React by leaning on HTMX (already loaded) for partial swaps and Alpine for local UI state.

## Goals

- Single `TableView` mixin + `<table>` partial powers all list views consistently.
- All interactions (sort, filter, paginate, bulk action) round-trip through HTMX swaps — no full page reloads, no JS framework.
- Column visibility persists per-user; saved views (filter+sort combos) persist per-user-per-table.
- Three export formats (CSV, XLSX, PDF) work on the *current filtered set*, not just all rows.
- Lighthouse perf ≥ 95 on a 1000-row Customers list.
- All upgraded list views ship with at least one bulk action that's not "delete".

## Non-goals

- Inline cell editing (defer; Phase 12 form widgets land first, then a follow-up).
- Drag-to-reorder columns (defer; use the visibility menu for now).
- Client-side virtual scroll (server-paginate instead — keeps it simple, good for SEO/printing).
- Cross-table joins / pivot tables.
- User-defined custom columns (computed columns from JSON path) — out of scope.
- Real-time row updates via Channels (Phase 14 may add a follow-up).

## Features

### Capabilities matrix

| Feature | Behaviour |
|---|---|
| **Pagination** | Server-side; cursor or page-number per `TableConfig.pagination`. Default 25 rows, configurable per table. URL reflects state (`?page=3&sort=-created_at&q=foo`). |
| **Sort** | Click column header to toggle asc → desc → unsorted. Multi-sort with Shift+click (up to 3 columns). |
| **Filter** | Per-column filter widgets declared in `Column` definition: text, select, multi-select, daterange, numeric range, boolean. Top-of-table search box does global text search across `searchable` columns. |
| **Column visibility** | Dropdown lists every column with checkbox; selection persists in `UserPreference` JSON. Required columns can be marked `pinned=True` (cannot hide). |
| **Sticky** | Header always sticky. First column optionally sticky-left, last column optionally sticky-right (e.g. for an actions column). |
| **Responsive** | Columns marked `priority=1..3` collapse below `md` / `sm` / `xs` breakpoints. Below `xs` the table renders as stacked cards via a separate partial. |
| **Row selection** | Checkbox per row + "select all on page" + "select all matching filter (X rows)". Selection state lives in Alpine for the page; bulk action POSTs the ID list. |
| **Bulk actions** | View declares `bulk_actions = [...]`; toolbar appears above the table when ≥ 1 row selected. Each action is a `(label, slug, confirm_text, handler)` tuple. |
| **Saved views** | "Save current view" → name → persisted in `SavedView(user, table_key, name, params_json, is_default)`. View dropdown lets user switch / delete / set default. |
| **Exports** | "Export" button with menu: CSV (always), XLSX (`openpyxl`), PDF (WeasyPrint, reusing `apps/invoices/pdf.py` infra). Exports honor current filter+sort, ignore pagination. |
| **Keyboard** | ↑↓ moves row focus, Space toggles selection, Enter opens detail, Cmd/Ctrl+A selects all on page, `/` focuses search. |
| **Empty states** | Renders `_empty_state.html` variants: "No data yet" (zero rows total), "No results" (zero after filter), "Filter too restrictive" with "Clear filters" button. |
| **Loading** | HTMX swap shows skeleton rows for >200ms responses (uses Phase 10 skeleton primitive). |

### Tables upgraded in this phase

| List view | Notable bulk actions | Notable filters |
|---|---|---|
| Customers | Tag, assign owner, archive, delete | Tag, owner, status, created date |
| Orders | Mark fulfilled, cancel, export selected | Status, customer, date range, amount range |
| Invoices | Mark paid, void, send reminder | Status, customer, due date, amount |
| Products | Toggle active, change category, delete | Category, active, price range, stock |
| Users | Change role, deactivate, reset password | Role, is_staff, is_active, last_login |
| Activity log | Export selected | Actor, event type, date range, target type |

### Demo page upgrade

`templates/pages/datatable.html` becomes the canonical reference: 1000 seeded demo rows, every feature on, columns demonstrating each filter/widget type. Acts as the "kitchen sink" for buyers.

## Architecture

### URLs

No new top-level routes. The datatable is an opt-in mixin applied to existing list views. Each list view gains:

```text
/<entity>/                  → full page (HTML)
/<entity>/?_partial=table   → table partial only (HTMX target)
/<entity>/export.csv        → CSV export of current filter
/<entity>/export.xlsx       → XLSX export
/<entity>/export.pdf        → PDF export
/<entity>/views/            → POST creates SavedView, GET lists user's views
/<entity>/views/<id>/       → DELETE removes
```

Implemented as URL params on the same view class (no separate URL entries needed except the views CRUD).

### App layout

```text
apps/core/tables/
├── __init__.py
├── config.py            TableConfig, Column, Filter, BulkAction dataclasses
├── views.py             TableView mixin
├── exporters.py         to_csv(), to_xlsx(), to_pdf()
├── filters.py           apply_filters() — translates query params → ORM filters
├── prefs.py             column visibility persistence helpers
└── tests/
    ├── test_config.py
    ├── test_views.py
    ├── test_exporters.py
    └── test_filters.py

apps/core/models.py adds:
    UserPreference        (user, key, value_json) — generic key/value
    SavedView             (user, table_key, name, params_json, is_default, created_at)

templates/core/tables/
├── _table.html          main partial (header + rows + footer + pagination)
├── _row.html            single row, included in a loop
├── _row_card.html       below-xs stacked card variant
├── _toolbar.html        search + filter chips + bulk actions + view switcher + export menu + column visibility
├── _filter_<type>.html  text / select / multi / daterange / numeric / boolean
├── _empty.html          empty-state variants
├── _skeleton.html       loading skeleton rows
└── _pagination.html     prev/next + page numbers + per-page selector
```

### Public API

```python
# apps/core/tables/config.py
from dataclasses import dataclass, field
from typing import Callable, Literal

@dataclass(frozen=True)
class Column:
    key: str                              # ORM field path or annotation key
    label: str                            # column header text
    sortable: bool = True
    searchable: bool = False              # included in global search
    filter: "Filter | None" = None        # per-column filter widget
    align: Literal["left", "right", "center"] = "left"
    width: str | None = None              # CSS value, e.g. "8rem"
    priority: int = 1                     # 1=always, 2=hide<md, 3=hide<sm
    pinned: bool = False                  # cannot be hidden via visibility menu
    formatter: Callable | None = None     # value -> rendered HTML (defaults to str())
    template: str | None = None           # override: render via {% include template %}

@dataclass(frozen=True)
class Filter:
    kind: Literal["text", "select", "multi", "daterange", "numeric", "boolean"]
    label: str | None = None
    choices: tuple = ()                   # for select/multi
    placeholder: str = ""

@dataclass(frozen=True)
class BulkAction:
    slug: str                             # POST identifier
    label: str
    confirm_text: str | None = None       # if set, shows confirm dialog
    icon: str = ""                        # lucide icon name
    destructive: bool = False             # styled red

@dataclass(frozen=True)
class TableConfig:
    key: str                              # unique identifier, used for prefs/views storage
    columns: tuple[Column, ...]
    bulk_actions: tuple[BulkAction, ...] = ()
    default_sort: str = "-id"
    page_size: int = 25
    sticky_first: bool = False
    sticky_last: bool = False
    row_url: Callable | None = None       # row -> detail URL (Enter / row click)
    exports: tuple = ("csv", "xlsx", "pdf")
```

### TableView mixin

```python
# apps/core/tables/views.py
from django.views.generic import ListView

class TableView(ListView):
    table_config: TableConfig             # subclass must define

    def get_queryset(self):
        qs = super().get_queryset()
        qs = apply_filters(qs, self.request.GET, self.table_config)
        qs = apply_sort(qs, self.request.GET, self.table_config)
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get("_partial") == "table":
            self.template_name = "core/tables/_table.html"
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Bulk action: dispatch by slug
        slug = request.POST.get("action")
        ids = request.POST.getlist("ids")
        action = next((a for a in self.table_config.bulk_actions if a.slug == slug), None)
        if action is None:
            return HttpResponseBadRequest()
        return self.handle_bulk_action(action, ids)

    def handle_bulk_action(self, action, ids):
        raise NotImplementedError("Subclass must implement.")
```

Per-view subclasses look like:

```python
class CustomerListView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      StaffRequiredMixin, TableView):
    model = Customer
    table_config = TableConfig(
        key="customers",
        columns=(
            Column("name", "Name", searchable=True, pinned=True),
            Column("email", "Email", searchable=True),
            Column("status", "Status", filter=Filter("select", choices=Customer.STATUS_CHOICES)),
            Column("owner.name", "Owner", filter=Filter("select", choices=lazy_owner_choices)),
            Column("created_at", "Created", filter=Filter("daterange")),
        ),
        bulk_actions=(
            BulkAction("tag", "Tag…", icon="tag"),
            BulkAction("archive", "Archive", icon="archive", confirm_text="Archive {n} customers?"),
            BulkAction("delete", "Delete", icon="trash-2", destructive=True,
                       confirm_text="Delete {n} customers? This cannot be undone."),
        ),
        sticky_first=True,
        row_url=lambda c: c.get_absolute_url(),
    )

    def handle_bulk_action(self, action, ids):
        qs = self.get_queryset().filter(pk__in=ids)
        if action.slug == "delete":
            count = qs.count()
            qs.delete()
            toast(self.request, messages.SUCCESS, f"Deleted {count} customers.")
        # ... etc
        return redirect(request.path)
```

### Exports

```python
# apps/core/tables/exporters.py
def to_csv(queryset, columns) -> HttpResponse: ...
def to_xlsx(queryset, columns) -> HttpResponse: ...   # openpyxl
def to_pdf(queryset, columns, *, title) -> HttpResponse: ...   # WeasyPrint
```

PDF export uses a shared `templates/core/tables/_export.html` table layout. New dep: `openpyxl>=3.1` in `pyproject.toml`.

### Models

```python
class UserPreference(models.Model):
    user = FK(User, on_delete=CASCADE)
    key = CharField(max_length=128)        # e.g. "table.customers.visible_columns"
    value = JSONField(default=dict)
    class Meta: unique_together = [("user", "key")]

class SavedView(models.Model):
    user = FK(User, on_delete=CASCADE)
    table_key = CharField(max_length=64)   # matches TableConfig.key
    name = CharField(max_length=80)
    params = JSONField(default=dict)       # filter/sort params
    is_default = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["table_key", "name"]
        constraints = [
            UniqueConstraint(fields=["user", "table_key", "name"],
                             name="uniq_savedview_per_table_per_user"),
        ]
```

### HTMX wiring

Toolbar inputs use `hx-get="?{{ current_params }}" hx-target="#table-region" hx-swap="outerHTML" hx-include="closest form" hx-push-url="true"`. Sort headers are anchors with the same pattern. Pagination links likewise. Bulk-action submit is `hx-post`. Saved-view switch is `hx-get` to the saved view's params. Result: every interaction swaps the `_table.html` partial only, URL stays canonical, browser back/forward works.

### Demo data

Bump `seed_demo` to create 1000 customers, 500 orders, 300 invoices, 200 products. Use Faker locale `en_US` plus `de_DE` for variety. Keep existing 15 users.

## Testing

### Unit (~25 new tests)

- `apply_filters`: each filter kind translates to expected ORM Q.
- `apply_sort`: single + multi-sort + invalid column rejected.
- `TableView.get`: returns full template normally, `_table.html` when `_partial=table`.
- `TableView.post`: dispatches to correct bulk action; rejects unknown slug; respects ids list.
- Exporters: CSV/XLSX/PDF return correct content-type, headers, row count matches queryset.
- `UserPreference` get/set helpers.
- `SavedView` constraint: cannot duplicate name per table per user.
- Column visibility prefs persist + load.
- Pagination URL reflects state, page-out-of-range falls back to last page.

### View tests (~10 new tests across upgraded list views)

- Customer list filters by status, sorts by name, paginates 1000 rows.
- Customer bulk delete removes selected, shows toast.
- Customer CSV export: row count matches filtered queryset.
- Same trio for Orders, Invoices, Products, Users (smoke depth).

### E2E (~6 new tests, marked `e2e`)

- Customers: load page, filter by status, sort by created date, paginate to page 3 — all via HTMX swaps (no full reload assertion via document.readyState observer).
- Customers: select 5 rows, click bulk archive, confirm, assert toast + rows gone.
- Customers: save view "Active in Q1", reload, assert view appears in switcher and applies its filter.
- Customers: column visibility — hide email column, reload page, email still hidden (pref persisted).
- Customers: export CSV, assert downloaded file has expected header row + N data rows.
- Datatable kitchen-sink page: every filter widget interacts; keyboard nav (`/`, ↑↓, Space, Enter) all work.

### Performance

Lighthouse run on Customers list with 1000 rows seeded: target perf ≥ 95. Capture a baseline run before optimizations and document any indexes added.

## Dependencies

- `openpyxl>=3.1` — XLSX export.
- `Faker>=22` — already a transitive of factory-boy in dev; pin explicitly.
- No new frontend deps. HTMX + Alpine carry the load.

## Rollout — 8 commits

1. **docs** — this spec.
2. **scaffolding** — `apps/core/tables/` package, `UserPreference` + `SavedView` models + migrations, base templates, no per-view wiring yet.
3. **read path** — pagination, sort, filter, search, column visibility, empty states, skeleton loading. Wire Customers list as proof. Tests for the read path.
4. **bulk actions** — selection model, toolbar, action dispatch, confirm dialogs (using Phase 10 modal). Wire Customers bulk archive + delete + tag.
5. **saved views** — model done in step 2; ship UI, switcher, default-view application. Tests.
6. **exports** — CSV, XLSX, PDF; export menu in toolbar; tests.
7. **upgrade remaining tables** — Orders, Invoices, Products, Users, Activity log; per-view tests.
8. **demo data + kitchen sink + screenshots + E2E** — bump `seed_demo`, rewrite `pages/datatable.html`, add 6 E2E tests, refresh screenshots, README/CHANGELOG entries, Lighthouse evidence captured in PR description.

## Branch + parent

- Branch: `phase11-datatable`
- Parent: `phase10-components` (depends on Phase 10's modal and skeleton primitives)

## Open questions

- **Cursor vs. page-number pagination?** Page numbers are friendlier for buyers eyeballing the demo. Cursor is faster on huge sets. Suggest: page-number default, cursor opt-in via `TableConfig.pagination="cursor"`.
- **PDF export for 1000 rows?** WeasyPrint can choke. Suggest: cap PDF export at 500 rows with a warning if exceeded; CSV/XLSX have no cap.
- **Filter UI placement?** Inline under each column header (compact, scannable) or in a side drawer (more room for complex filters)? Suggest: chips above the table for active filters + a "Filters" button opening a drawer for editing — this scales to many filters without crowding column headers.
- **Should saved views be shareable across the org?** Out of scope for Phase 11; revisit after Phase 16 ships orgs.
