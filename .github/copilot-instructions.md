# GitHub Copilot Instructions — Apex Dashboard (Django)

Django 6.0 + Tailwind v4 + Alpine.js + HTMX + Channels (ASGI/Daphne). v0.18.2, 27 apps + Apex-themed Django Admin, 1034+ tests, multi-tenant, REST API via Django Ninja, realtime via WebSockets. Python 3.12–3.14, `uv` for deps. Server-rendered, no SPA. Full reference: `CLAUDE.md`.

## Hard rules

- **Generic CBVs** for non-API views. Function views only for chart JSON / Ninja API.
- **Use `TableView`** (`apps/core/tables/views.py:37`) for list pages — not `ListView`. You get sort/filter/paginate/export/bulk/column-vis/saved-views for free. Define `<NAME>_TABLE = TableConfig(...)` alongside the view; subclass `TableView`; implement `handle_bulk_action(action, ids, request)` if needed.
- **Mixin order**: `BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, [StaffRequiredMixin,] [OrgRequiredMixin, OrgScopedMixin,] [HasRoleMixin,] [PasswordConfirmationRequiredMixin,] <View>`.
- **Custom User**. `get_user_model()` or `from apps.accounts.models import User`. Never `django.contrib.auth.models.User`.
- **`Customer` ≠ `User`.** User = internal team. Customer = external. FK accordingly.
- **URL namespacing**. Every `urls.py` sets `app_name`. Reverse `app:name`.
- **Forms apply per-app `BASE_INPUT`** in `__init__`. Intentionally duplicated per app — don't consolidate.
- **Org scoping is opt-in.** Apply `OrgRequiredMixin + OrgScopedMixin` per view; middleware sets `request.organization` but doesn't filter queries.
- **Realtime dispatch**: `apps.realtime.dispatch.push_notification(user_id, payload)`. No-ops without channel layer — safe everywhere.
- **Notifications**: `apps.notifications.dispatch.notify(user, category, ...)` — not `Notification.objects.create()`. Categories: `system|billing|mention|comment|security`.
- **API**: cursor pagination (`?cursor=<id>&limit=N`, max 100), bearer auth (`Authorization: Bearer apex_<token>`).
- **Webhooks**: HMAC-SHA256 over canonical JSON, header `X-Apex-Signature`.
- **Soft-delete** for `Customer`, `Project`, `File`. `Customer.objects` hides archived; `Customer.all_objects` unfiltered. Don't change `Meta.base_manager_name`.
- **Tailwind v4**, no config. Tokens in `static_src/css/input.css`. Rebuild: `npm run build`. Never edit `static/css/app.css` (gitignored output).
- **Translations**: `gettext_lazy` on nav/forms. `str()` before JSON/assert.
- **CDN scripts have SRI hashes** in `templates/base.html`. Regenerate `integrity=` on version bump.
- **Admin theme**: `from apex.admin import ModelAdmin, TabularInline, StackedInline` (not `admin.ModelAdmin`). Set `show_in_dashboard = True` + `apex_icon = "<lucide-name>"` to surface a stat card on `/admin/`. Theme is registered ABOVE `django.contrib.admin` in `INSTALLED_APPS`.

## File layout

- `apex/settings/{base,dev,prod,mssql}.py` — split settings; `base.SECRET_KEY = None` intentionally.
- `apex/asgi.py` — HTTP + WS routing.
- `apps/<name>/` — 27 apps, self-contained (`models.py`, `forms.py`, `views.py`, `urls.py`, `tests/`, sometimes `api.py`).
- `apps/core/navigation.py` — `NAV_ITEMS`, 7 groups.
- `apps/core/tables/` — datatable system (`TableView`, `TableConfig`, `Column`, `Filter`, `BulkAction`).
- `apps/core/templatetags/apex.py` — `{% icon %}` + `ICONS` dict.
- `apps/realtime/` — Channels consumers + dispatch.
- `apps/api/` — Django Ninja router, KeyAuth, cursor pagination, webhook model.
- `apps/organizations/` — Org + Membership + Invitation + mixins + middleware.
- `templates/` — project-level; `layouts/dashboard.html` is the standard parent.
- `static_src/css/input.css` — Tailwind input (edit this).
- `static/css/app.css` — Tailwind output (don't edit).
- `static/js/{charts,realtime,shell,pwa,app}.js`.

## Anti-patterns

- Don't write a plain `ListView` — use `TableView`.
- Don't `Notification.objects.create()` directly — use `notify()`.
- Don't paginate the API with `?page=` — cursor only.
- Don't add jQuery, Bootstrap, or icon-font libs.
- Don't downgrade to WSGI — Channels needs ASGI/Daphne.
- Don't bypass `KeyAuth` for API endpoints.
- Don't FK to `User` for external people — use `Customer`.
- Don't JSON-serialize `gettext_lazy` proxies — coerce with `str()`.
- Don't hand-edit sidebar templates — append to `NAV_ITEMS`.
- Don't import `admin.ModelAdmin` for new admins — use `apex.admin.ModelAdmin`.
- Don't render `{% for m in messages %}` in admin templates — `{% apex_toasts %}` consumes them already.

## Commands

```bash
uv sync --all-groups
npm install && npm run build
uv run python manage.py migrate
uv run python manage.py seed_demo                # demo / ApexShowcase!2026
uv run python manage.py runserver
uv run pytest                                    # 1034 unit tests, e2e excluded
uv run pytest -m e2e                             # Playwright Chromium
uv run ruff check . && uv run ruff format .
```

## When generating code

- Match `apps/customers/views.py` for new `TableView` subclasses (it's the canonical reference).
- Match `apps/customers/forms.py` for new `ModelForm` widgets with `BASE_INPUT`.
- Match `static/js/charts.js` patterns for new charts (use `themeColors()` + `MutationObserver` for dark-mode redraw).
- Add new sidebar entries to `NAV_ITEMS`, register new icons in `ICONS`.
- API endpoints go in `apps/<feature>/api.py` as a `Router`, attached in `apps/api/api.py`.
