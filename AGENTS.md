# AGENTS.md

Cross-tool agent instructions for Apex Dashboard (Django edition). Read by Aider, Cline, Codex, Continue, and any tool following the [agents.md](https://agents.md) convention. Claude Code reads `CLAUDE.md`; Cursor reads `.cursor/rules/`; Copilot reads `.github/copilot-instructions.md`. Content is intentionally overlapping — each tool only sees its own file.

## What this is

Django 6.0 admin dashboard, v0.18.2. Server-rendered HTML, no SPA. Tailwind v4 + Alpine.js + HTMX + Channels (ASGI/Daphne). 27 Django apps + Apex-themed Django Admin, 1034+ unit tests, multi-tenant orgs, REST API (Django Ninja), realtime via WebSockets, multi-language (en + es). Python 3.12–3.14, deps via `uv`.

Live demo: `https://apex-django.dashboardpack.com/` — `demo` / `ApexShowcase!2026`.

## Setup

```bash
uv sync --all-groups
npm install && npm run build
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver
```

Dev runs two processes: `npm run dev` (Tailwind watch) and `uv run python manage.py runserver`.

## Tests

```bash
uv run pytest                          # 1034 unit tests (~90s); e2e excluded
uv run pytest apps/invoices/tests/     # one app
uv run pytest -m e2e                   # Playwright Chromium
```

`pyproject.toml` pins `DJANGO_SETTINGS_MODULE = apex.settings.dev` and excludes e2e from default runs via `addopts`.

## Architecture (the load-bearing pieces)

- **Settings split** (`apex/settings/`): `base.py` (shared, `SECRET_KEY = None` intentionally), `dev.py` (SQLite, console email, `DEMO_MODE`), `prod.py` (parses `postgres://` / `mssql://` / `sqlserver://`; opt-in Sentry/Prometheus/Redis), `mssql.py` (alternative; `prod.py` handles MSSQL natively).
- **ASGI by default.** `apex/asgi.py` routes HTTP → Django, WS → `AuthMiddlewareStack` → `URLRouter` wrapped in `AllowedHostsOriginValidator`. Channels layer: in-memory dev, Redis prod (when `REDIS_URL` set).
- **27 apps** under `apps/<name>`, all registered as `apps.<name>` in `INSTALLED_APPS`. Categories: foundation (`core`, `accounts`), commerce (`customers`, `products`, `orders`, `invoices`, `billing`), collaboration (`mail`, `chat`, `notifications`, `activity`), productivity (`events`, `kanban`, `projects`, `files`, `wizard`), tenancy + realtime (`organizations`, `realtime`), surfaces (`dashboard`, `marketing`, `blog`, `help`, `docs`, `profiles`, `components`), platform (`api`).
- **Custom User model** in `apps.accounts.models.User` — has `email_verified_at`, `role`, profile fields.
- **`Customer` ≠ `User`.** User is internal team; Customer is external. FK accordingly.
- **Single sources of truth**:
  - `apps/core/navigation.py` (`NAV_ITEMS`, 7 groups, `requires_staff` gating).
  - `apps/core/templatetags/apex.py` (`ICONS` dict, `{% icon %}` is the only icon path).
  - `apps/core/tables/` (datatable system used by every major list view).

## Conventions

1. **Generic CBVs.** Function views only for chart JSON / Ninja API endpoints.
2. **`TableView` for list views** (`apps/core/tables/views.py:37`) — subclass it, not `ListView`. Get sort/filter/paginate/export/bulk/column-vis/saved-views for free.
3. **Mixin order**: `BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, [StaffRequiredMixin,] [OrgRequiredMixin, OrgScopedMixin,] [HasRoleMixin,] [PasswordConfirmationRequiredMixin,] <GenericView>`.
4. **Custom User** — `get_user_model()` or `from apps.accounts.models import User`. Never `django.contrib.auth.models.User`.
5. **URL namespacing**. `app_name = "<app>"` in every `urls.py`. Reverse as `app:name`.
6. **Forms apply per-app `BASE_INPUT`** Tailwind class string in `__init__`. Intentionally duplicated per app — don't consolidate.
7. **Org scoping is opt-in.** `OrganizationMiddleware` sets `request.organization` for every authed request but doesn't filter queries. Apply `OrgRequiredMixin + OrgScopedMixin` per view.
8. **Realtime dispatch is fire-and-forget.** `apps.realtime.dispatch.push_notification(user_id, payload)` / `push_unread_count(user_id, count)` no-op without a layer. Safe to call anywhere.
9. **`apps.notifications.dispatch.notify(user, category, ...)` for notifications** — not `Notification.objects.create()` (you'd skip realtime fan-out).
10. **API uses cursor pagination** (`?cursor=<id>&limit=N`, max 100). Not `?page=`.
11. **Webhook payloads use canonical JSON** (sorted keys, no whitespace) via `serialize_event_payload()`. Sign with `HMAC-SHA256(secret, body)` in header `X-Apex-Signature`.
12. **Soft-delete defaults**: `Customer`, `Project`, `File` (and others). Use `<Model>.all_objects` for unfiltered access. `Meta.base_manager_name = "all_objects"` keeps FK traversal working — don't change it.
13. **Tailwind v4, no config file.** Tokens in `static_src/css/input.css` (`@theme inline` + `:root`/`.dark`). Content paths via `@source`. Rebuild: `npm run build`.
14. **Translations**: `gettext_lazy` on nav/forms. `str()` before JSON or assertions.
15. **CDN scripts have SRI hashes** in `templates/base.html`. Regenerate `integrity=` on version bump.

## Mixin catalog

- `BreadcrumbsMixin` (`apps/core/breadcrumbs.py`) — set `breadcrumb_title`, `breadcrumb_parent`.
- `EmailVerifiedRequiredMixin`, `PasswordConfirmationRequiredMixin` (`apps/accounts/mixins.py`).
- `StaffRequiredMixin` (`apps/accounts/views.py:60`).
- `OrgRequiredMixin`, `HasRoleMixin`, `OrgScopedMixin` (`apps/organizations/mixins.py`).
- `TableView` (`apps/core/tables/views.py:37`).

## Datatable system

The single most-used architectural piece. Every list view (Customers, Orders, Invoices, Products, Users, Activity) subclasses `TableView`. Define a `TableConfig` with `Column`/`Filter`/`BulkAction`, override `handle_bulk_action()` if needed. Filter widgets: text, select, daterange, numeric, boolean. Exports: CSV/XLSX/PDF (PDF capped at 500 rows). Column visibility persisted per-user via `UserPreference`. Reference: `apps/customers/views.py:18`.

## Realtime (Channels)

Consumers in `apps/realtime/consumers.py`: `NotificationConsumer` (`/ws/notifications/`, group `notify.user.<id>`), `PresenceConsumer` (`/ws/presence/`). Both reject anonymous (close 4401). Server dispatches via `push_notification(user_id, payload)`. Client: `apexNotifyStream()` / `apexPresence()` Alpine factories in `static/js/realtime.js` with exponential backoff.

## API (Django Ninja)

`/api/v1/`, Swagger UI at `/api/docs/`. Bearer auth (`Authorization: Bearer apex_<token>`); `APIKey` model stores SHA-256 hash + 8-char prefix. Routers: customers, products, orders, invoices, notifications, webhooks. Cursor pagination. Webhooks signed with HMAC-SHA256, delivery log via `WebhookDelivery`.

## Organizations / RBAC

`Organization` + `Membership` (5 roles: owner > admin > billing > member > viewer) + `Invitation` (opaque token, 14-day TTL, idempotent `accept()`). `OrganizationMiddleware` sets `request.organization` post-auth. Resolution: session slug → first membership alphabetically → None.

## Admin theme (`apex.admin`)

Django Admin at `/admin/` is re-skinned to match the rest of Apex — same sidebar, header, dark mode, command palette, toasts. The theme lives in `apex/admin/` (registered in `INSTALLED_APPS` ABOVE `django.contrib.admin`) plus `templates/admin/` + `static_src/css/admin.css` (scoped to `.apex-admin`).

Use the themed base classes when adding a new admin:

```python
from django.contrib import admin
from apex.admin import ModelAdmin, TabularInline

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    show_in_dashboard = True      # surfaces a stat card on /admin/
    apex_icon = "package"         # Lucide icon name (apps/core/templatetags/apex.py)
    list_display = ("name", "price", "stock")
```

Gotchas: Django admin blocks (`pretitle`/`content_title`/`content`/`object-tools`/`sidebar`) must be declared exactly ONCE in `templates/admin/base.html` — duplicates error even in mutually-exclusive `{% if %}` branches. `{% block object-tools %}` is nested inside `{% block content %}` (matches Django stock). Admin messages flow through `{% apex_toasts %}`; don't also render a `{% for m in messages %}` loop — `get_messages()` consumes on iteration.

## Settings / env vars

Required in prod: `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`. Optional: `REDIS_URL` (upgrades Channels + cache), `SENTRY_DSN`, `METRICS_ENABLED`, `DEMO_MODE`, `EMBED_PARENT_ORIGINS`. MSSQL: `mssql://user:pass@host:1433/db?driver=ODBC+Driver+18+for+SQL+Server`; requires `uv sync --extra mssql` + Microsoft ODBC Driver 18.

## Recipes

### New CRUD module backed by `TableView`

1. `apps/widgets/{models,forms,views,urls}.py` — model, form (applies `BASE_INPUT`), `TableView` subclass with `WIDGETS_TABLE = TableConfig(...)`, `app_name = "widgets"`.
2. `apex/settings/base.py` — append `"apps.widgets"` to `INSTALLED_APPS`.
3. `apex/urls.py` — include the app.
4. `apps/core/navigation.py` — add `NavItem(...)` to the right group; register icon in `ICONS` if new.
5. `templates/widgets/widget_{list,detail,form}.html` extending `layouts/dashboard.html`. List template renders the shared table partial.
6. `apps/widgets/tests/factories.py`; wire into `seed_demo` if you want demo rows.
7. `uv run python manage.py makemigrations widgets && migrate`.

### Opt a model into org scoping

1. Add nullable `organization = ForeignKey(Organization, null=True, ...)`. Migrate.
2. Backfill via data migration.
3. On list/detail views, append `OrgRequiredMixin, OrgScopedMixin` to bases.
4. On create views, set `form.instance.organization = self.request.organization` in `form_valid`.

### New API endpoint

1. `apps/<feature>/api.py` — `router = Router()` with `ninja.Schema` types and the cursor pagination helper from `apps/api/pagination.py`.
2. `apps/api/api.py` — `api.add_router("/<feature>/", "apps.<feature>.api.router")`.
3. Auth is automatic; `request.auth_user` is the authenticated user.

### Wire a notification

`apps.notifications.dispatch.notify(user, category, title, body, url, **meta)` — creates the row and fans out via Channels. Categories: `system | billing | mention | comment | security`.

### New chart

JSON endpoint → Alpine factory in `static/js/charts.js` using `themeColors()` + `MutationObserver` (ApexCharts can't read OKLCh CSS vars) → `window.myChart = myChart` → template `<div x-data="myChart()" x-init="init()">`.

## Anti-patterns

- Don't edit `static/css/app.css` (gitignored). Edit `static_src/css/input.css`.
- Don't hand-edit sidebar templates — append to `NAV_ITEMS`.
- Don't write plain `ListView` for a list page — use `TableView`.
- Don't add jQuery / Bootstrap / icon-font libs.
- Don't `from django.contrib.auth.models import User` — use `get_user_model()`.
- Don't FK to `User` for external people — use `Customer`.
- Don't consolidate `BASE_INPUT` into a shared module (per-app duplication is current convention).
- Don't assume queries are org-scoped — apply `OrgScopedMixin` explicitly.
- Don't paginate the API with `?page=` — cursor only.
- Don't `Notification.objects.create()` directly — use `notify()`.
- Don't downgrade to WSGI — Channels needs ASGI/Daphne.
- Don't bump CDN versions without regenerating SRI hashes.
- Don't bypass `KeyAuth` for API endpoints.
- Don't JSON-serialize `gettext_lazy` proxies — coerce with `str()`.

## Demo data (`seed_demo`)

Login: `demo` / `ApexShowcase!2026` (configurable via `DEMO_USERNAME`/`DEMO_PASSWORD` settings). Creates: 15 users, 100 customers, 25 products, 30 orders, 15 invoices, ~30 mails, 12 calendar events, ~22 kanban cards, sample files, 6 projects, 19 help articles, 9 blog posts, 3 chat threads, 3 organizations (demo owns all), Pro subscription + 2 payment methods.

Idempotent for demo user; additive otherwise. `rm db.sqlite3 && migrate && seed_demo` for a clean slate.

## CI

`.github/workflows/ci.yml` — `lint-and-test` (ruff + `manage.py check` + `pytest apps/ -q`; installs WeasyPrint system deps + `compilemessages`) + `e2e` (Playwright Chromium against `tests/e2e/`).
