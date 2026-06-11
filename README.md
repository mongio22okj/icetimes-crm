# Apex Dashboard — Django Edition

[![CI](https://github.com/puikinsh/dashboardpack-apex-django/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/puikinsh/dashboardpack-apex-django/actions/workflows/ci.yml)
![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![Tests](https://img.shields.io/badge/tests-1024%20passing-success)

A production-ready admin dashboard built on **Django 6** with server-rendered HTML and no heavy JavaScript framework. **Twenty-three apps · 5 dashboard variants · 1035 unit tests**, multi-locale, dark mode, multi-tenant orgs, realtime via Channels, hosted docs, CSP, Sentry-ready, PWA-installable — out of the box.

[**Live demo →**](https://apex-django.dashboardpack.com/)  ·  Sign in with `demo` / `ApexShowcase!2026` (auto-filled).

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/puikinsh/dashboardpack-apex-django)
[![Deploy on Fly.io](https://img.shields.io/badge/Deploy_on-Fly.io-7c3aed?logo=fly.io&logoColor=white)](https://fly.io/launch?from=https://github.com/puikinsh/dashboardpack-apex-django)

![Apex Dashboard](screenshots/dashboard.png)

---

## What you get

### Dashboards (5 variants)

| Variant | What's in it |
|---|---|
| **Overview** | Stats cards · revenue chart · traffic donut · goals · recent orders · activity feed |
| **Analytics** | Page Views · Unique Visitors · Bounce Rate · Avg Session · Top Pages · Top Countries |
| **CRM** | Pipeline · Deal Stages · Top Sales Reps · Lead Sources · Recent Deals · Quarterly Targets |
| **eCommerce** | Sales Overview · Order Status · Top Products · Sales by Category · Recent Transactions |
| **SaaS** | MRR/ARR Growth · Subscription Plans · Marketing Channels · User Growth · Recent Signups |

### Apps

| Surface | What's in it |
|---|---|
| **Auth** | Login · register · password reset · email verification · 2FA (TOTP + recovery codes) · sudo-mode confirm-password · session lock-screen |
| **Customers** | Soft-delete CRUD · staff-gated · avatar uploads · order history per customer |
| **Invoices** | INV-YYYY-NNNN auto-numbering · DRAFT→SENT→PAID/VOID state machine · WeasyPrint PDF · UUID-token public sharing · generate from order |
| **Orders** | Cart-style line items · status state machine · invoice generation · soft-delete archive |
| **Products** | Catalog · categories · stock tracking · SKU-based identifiers |
| **Mail** | Three-pane inbox · 5 folders (Inbox/Sent/Drafts/Starred/Trash) · reply threading · star/trash · new-mail notifications |
| **Chat** | 1:1 conversations · HTMX-polled message stream · mark-read on view |
| **Calendar** | FullCalendar v6 · month/week/day · 4 color categories · click-to-create · JSON event source |
| **Kanban** | 4-column board · SortableJS drag-and-drop · priority borders · assignees · due dates |
| **Projects** | Project + Tasks + Milestones · 4-tab detail (Overview / Tasks / Team / Activity) · per-project task board · milestone toggle |
| **Profiles** | Public-facing rich profile · directory · 4 tabs (Overview / Projects / Activity / Connections) · shared-project teammates |
| **Activity log** | Workspace-wide event stream · signal-driven · date-grouped buckets · category + scope filters |
| **Files** | Per-user browser · folder hierarchy · 10MB upload cap · download with original filename |
| **Notifications** | HTMX-polled bell · unread badge · day-bucketed list · 5 categories (system / billing / mention / comment / security) with filter pills · per-row archive + restore · actor avatars · per-user × per-channel preferences page (in-app / email / browser push) · service worker + push subscription scaffold |
| **Billing** | Stripe-Customer-Portal-style: current plan · usage meters · payment methods · plan change · cancel/reactivate · billing history |

### Marketing & content

| Surface | What's in it |
|---|---|
| **Marketing landings** | 4 landing variants (Analytics/SaaS/CRM/eCommerce) · pricing page · support page with contact form |
| **Help center** | Knowledge base with 6 categories · 19 seeded articles · full-text search · related articles · view counters |
| **Blog** | Public marketing blog · topics · featured hero · author bylines · 9 seeded posts |
| **Wizard** | Multi-step session-backed onboarding form with progress indicator |

### Showcase (Metronic-parity reference pages)

| Page | What it demonstrates |
|---|---|
| **Components** | 26 reusable UI primitives across 7 categories (Overlay / Disclosure / Inputs / Choice / Upload / Feedback / Identity) — modal, drawer, toast, tabs, accordion, stepper, datepicker, multi-select, file dropzone, skeleton, spinner, progress ring, avatar, badge and more — each on its own page with copy-paste markup and accessibility notes |
| **Charts** | 8 ApexCharts variants (bar/line/area/donut/radial/heatmap/scatter/mixed) themed for light + dark |
| **Forms gallery** | 12 polished form widgets backing real Django form fields: floating-label inputs + textarea, icon prefix/suffix, multi-select with chips, free-form tag input, typeahead combobox (static + async), date range picker, drag-drop file dropzone with XHR progress, EasyMDE rich-text editor, character counter, conditional reveal · 4 validation states · 3 sizes |
| **Widgets gallery** | Stat cards · badges/pills · avatars · leaderboard · progress targets · timeline · buttons · empty states |
| **Datatable** | Reusable HTMX-driven table system powering Customers / Orders / Invoices / Products / Users / Activity. Server-side sort + 6 filter widgets (text/select/multi/daterange/numeric/boolean) + global search + bulk actions with confirm modal + saved views + per-user column visibility + CSV/XLSX/PDF export — all via HTMX swaps, no full reloads |
| **API docs** | Live REST API at `/api/v1/` (Django Ninja) with bearer-token auth · auto-generated Swagger UI at `/api/v1/docs` + OpenAPI schema at `/api/v1/openapi.json` · cursor pagination · CRUD over Customers / Products / Orders / Invoices / Notifications / Webhooks · signed outbound webhooks (HMAC-SHA256) wired into invoice transitions · `python manage.py create_api_key` to generate a token |
| **Maps** | Leaflet + OpenStreetMap · customer markers + popups · MRR-proportional density circles · dark-mode tile filter |
| **Coming Soon / Maintenance / 503** | Pre-launch countdown · scheduled-downtime · service-unavailable · branded auth-style pages |

### Account

| Surface | What's in it |
|---|---|
| **Settings** | 4-section nav: **Account** (profile, appearance) · **Security** (password, two-factor, active sessions with sign-out-others, audit log) · **Integrations** (API tokens with one-time reveal, webhooks with delivery log, notification preferences) · **Privacy** (GDPR-style data export ZIP, account deletion with typed-confirm + 30-day grace) |
| **Organizations** | Multi-tenant workspaces · header switcher · per-org settings + member roster · 5-tier RBAC (owner / admin / billing / member / viewer) · email invitations with 14-day TTL + public accept page · `OrgRequiredMixin` / `HasRoleMixin` / `OrgScopedMixin` for opt-in tenant-scoping |
| **Realtime** | Channels 4 + Daphne ASGI · live notification fan-out (bell badge updates without polling) · global presence pill · in-memory layer in dev (zero infra), Redis in prod via `REDIS_URL` · `/realtime/` demo with two-tab sync |
| **Users** | Admin-only user CRUD with role assignment |
| **Django Admin** | `/admin/` fully re-skinned to match Apex — same sidebar, header, dark mode, command palette, toasts. Drop-in `apex.admin.ModelAdmin` with `show_in_dashboard` stat cards + Lucide `apex_icon`s. Themed login, change list (empty states), change form (aligned grid, no label colons), inlines, FK widgets, Select2 autocomplete, M2M filter_horizontal, calendar popup, file/image inputs, popups, password change, 404/500. Existing `admin.ModelAdmin` registrations pick up the theme automatically. |
| **Team directory** | Browse profiles by role · KPI counts · search by name/email/title |
| **i18n** | English + Spanish locale bundled · header language picker · `gettext_lazy` across navigation |

Plus: command palette (Cmd+K), toast notifications wired into Django messages, accessible icons, breadcrumbs, mobile drawer, error pages (403/404/500), branded HTML email templates, demo mode with auto-fill login, seed data for everything above. Marketing site ships with a real changelog (`/landing/changelog/`), public roadmap, comparison table, showcase index, sitemap.xml, robots.txt, and OpenGraph + Twitter card meta on every page.

## Screenshots

### Dashboards

| Overview (light) | Overview (dark) |
|---|---|
| ![Dashboard](screenshots/dashboard.png) | ![Dashboard dark](screenshots/dashboard-dark.png) |

| Analytics | CRM |
|---|---|
| ![Analytics](screenshots/dashboard-analytics.png) | ![CRM](screenshots/dashboard-crm.png) |

| eCommerce | SaaS |
|---|---|
| ![eCommerce](screenshots/dashboard-ecommerce.png) | ![SaaS](screenshots/dashboard-saas.png) |

### Projects + Profiles

| Projects list | Project detail (overview) |
|---|---|
| ![Projects](screenshots/projects-list.png) | ![Project overview](screenshots/projects-overview.png) |

| Project tasks board | Team directory |
|---|---|
| ![Project tasks](screenshots/projects-tasks.png) | ![Team](screenshots/profiles-list.png) |

| Profile overview | Profile connections |
|---|---|
| ![Profile](screenshots/profiles-overview.png) | ![Connections](screenshots/profiles-connections.png) |

### Productivity apps

| Mail (three-pane inbox) | Kanban (drag-and-drop) |
|---|---|
| ![Mail](screenshots/mail-inbox.png) | ![Kanban](screenshots/kanban.png) |

| Calendar | Charts showcase |
|---|---|
| ![Calendar](screenshots/calendar.png) | ![Charts](screenshots/charts.png) |

| Activity log | Files |
|---|---|
| ![Activity](screenshots/activity-list.png) | ![Files](screenshots/files.png) |

### Commerce + billing

| Invoices | Customers |
|---|---|
| ![Invoices](screenshots/invoices-list.png) | ![Customers](screenshots/customers-list.png) |

| Billing overview | Plan comparison |
|---|---|
| ![Billing](screenshots/billing-overview.png) | ![Plans](screenshots/billing-plans.png) |

### Help center + Blog

| Help center | Help article |
|---|---|
| ![Help](screenshots/help-home.png) | ![Article](screenshots/help-article.png) |

| Blog list | Blog post |
|---|---|
| ![Blog](screenshots/blog-list.png) | ![Post](screenshots/blog-detail.png) |

### Showcase pages

| Datatable | API docs |
|---|---|
| ![Datatable](screenshots/pages-datatable.png) | ![API docs](screenshots/pages-api-docs.png) |

| Maps (Leaflet) | Forms gallery |
|---|---|
| ![Maps](screenshots/pages-maps.png) | ![Forms](screenshots/pages-forms.png) |

| Widgets gallery | Coming Soon |
|---|---|
| ![Widgets](screenshots/pages-widgets.png) | ![Coming Soon](screenshots/pages-coming-soon.png) |

### Marketing + auth

| Hub landing | Pricing |
|---|---|
| ![Landing hub](screenshots/landing-hub.png) | ![Pricing](screenshots/landing-pricing.png) |

| Login (with demo auto-fill) | 2FA setup |
|---|---|
| ![Login](screenshots/login.png) | ![Two-factor](screenshots/settings-2fa.png) |

---

## Tech stack

- **Django 5.1** (LTS-track, Python 3.12 / 3.13)
- **Tailwind CSS v4** with OKLCh design tokens — full dark mode
- **Alpine.js 3** + **HTMX 2** for progressive enhancement (no SPA build step)
- **ApexCharts** for all charts, **FullCalendar v6** for the calendar, **SortableJS** for kanban drag, **Leaflet** for maps (Maps page only — loaded via `head_extra`)
- **WeasyPrint** for invoice PDFs
- **pyotp** + **qrcode** for TOTP 2FA
- **pytest** (588 unit tests) + **Playwright** (57 E2E tests)

No SPA framework. No webpack. No Redis. No Celery. No node runtime in production.

## Quick start

### Option A — Docker (one command, Postgres bundled)

```bash
docker compose up
```

Open <http://localhost:8000/> and sign in with **demo / `ApexShowcase!2026`**. The first run migrates and seeds; subsequent runs reuse the database volume.

### Option B — Native (uv + npm + SQLite)

```bash
make setup    # install deps, build CSS, migrate, seed, compile translations
make run      # start dev server
```

Open <http://localhost:8000/> and sign in with **demo / `ApexShowcase!2026`**.

If you don't have `make`:

```bash
# 1. System libs (PDF rendering)
brew install cairo pango gdk-pixbuf libffi   # macOS
# apt-get install libpango-1.0-0 libpangoft2-1.0-0   # Debian/Ubuntu

# 2. Python deps via uv
uv sync --all-groups

# 3. Tailwind CSS build
npm install && npm run build

# 4. Database + demo data + translations
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py compilemessages

# 5. Run
uv run python manage.py runserver
```

> **Watch mode for active development:** `npm run dev` rebuilds the CSS as templates change. Run alongside `manage.py runserver`.

### Make targets

```text
make setup     One-time: install deps, build CSS, migrate, seed
make run       Start dev server
make test      Run unit tests
make e2e       Run Playwright E2E tests
make reseed    Drop SQLite DB + media + reseed
make build     Production CSS + collectstatic
make docker    Build + run via docker compose
make clean     Remove build artifacts
```

`make help` lists all targets.

## Running tests

```bash
# Unit tests — fast, no browser
uv run pytest

# End-to-end tests — spawns Chromium
uv run playwright install chromium    # one-time
uv run pytest -m e2e

# Full suite
./run-e2e.sh
```

**Counts:** 588 unit tests · 2 PDF tests skip without WeasyPrint native libs · 57 Playwright flows.

## Project layout

```text
apex/                Django project — settings/urls/wsgi
apps/
  accounts/          User model, auth views, 2FA, lock-screen middleware
  activity/          Global activity log + signal-driven event stream
  billing/           Subscription + PaymentMethod + plan changes
  blog/              Public marketing blog (Topic + Post)
  chat/              ChatMessage + 1:1 conversation views
  core/              Shared chrome (sidebar nav, breadcrumbs, icon templatetag,
                       error pages, status pages, showcase galleries, seed_demo)
  customers/         Customer model + soft-delete CRUD
  dashboard/         Overview + 4 dashboard variants (Analytics/CRM/eCommerce/SaaS)
                       + 8-chart showcase
  events/            Calendar (FullCalendar JSON source)
  files/             Folder + File browser
  help/              Help center / knowledge base (Category + Article)
  invoices/          Invoice + InvoiceItem + WeasyPrint PDF
  kanban/            Card model + SortableJS move endpoint
  mail/              Message model + three-pane mail
  marketing/         4 landing variants + pricing + support
  notifications/     Notification + dispatch helpers
  orders/            Order + OrderItem
  products/          Product + Category
  profiles/          Public profile pages (4-tab detail + directory)
  projects/          Project + Milestone + ProjectTask (4-tab detail)
  wizard/            Multi-step onboarding form

templates/           Shared templates (layouts/, partials/, components/, pages/)
static/              Built CSS + tracked JS sources
static_src/          Tailwind input.css with design tokens
locale/es/           Spanish translations
tests/e2e/           Playwright suite

docs/superpowers/    Per-phase design specs + implementation plans
                     (read these to understand how each app was built,
                      decisions, and trade-offs)
```

## Customization

### Design tokens

All colors live in `static_src/css/input.css` as OKLCh custom properties. Edit `:root` (light mode) or `.dark` blocks, run `npm run build`, refresh.

### Adding a new app

1. `mkdir apps/<name>` with `__init__.py`, `apps.py`, `models.py`, `views.py`, `urls.py`, `migrations/`, `tests/`.
2. Register in `apex/settings/base.py` `INSTALLED_APPS`.
3. Add `path("<name>/", include("apps.<name>.urls"))` in `apex/urls.py`.
4. Add a `NavItem(...)` to `apps/core/navigation.py`.
5. Generate migration, run tests, ship.

The 21 existing apps follow this pattern exactly — copy any of them as a template.

### Adding a chart

`static/js/charts.js` has the existing chart factories (`revenueChart`, `trafficChart`). Add a new factory function with `Alpine.data(...)`, then `<div x-data="myChart()">` in your template.

The full ApexCharts gallery lives at `/charts/` for reference.

### Adding a locale

```bash
uv run python manage.py makemessages -l fr --ignore=node_modules --ignore=.venv
# fill in locale/fr/LC_MESSAGES/django.po
uv run python manage.py compilemessages
```

Add the language tuple to `LANGUAGES` in `apex/settings/base.py` and the picker in the user dropdown will show it automatically.

### Registering a model in the themed Django Admin

`/admin/` is fully themed. Register models with the `apex.admin` base classes to pick up the extras:

```python
from django.contrib import admin
from apex.admin import ModelAdmin, TabularInline   # or StackedInline

@admin.register(MyModel)
class MyModelAdmin(ModelAdmin):
    show_in_dashboard = True     # stat card on /admin/ with live count
    apex_icon = "package"        # Lucide icon name (apps/core/templatetags/apex.py)
    list_display = ("name", "price", "created_at")
```

Plain `admin.ModelAdmin` registrations also get the theme automatically via the template overrides in `templates/admin/` — `apex.admin.ModelAdmin` is purely the hook for the opt-in conveniences (`show_in_dashboard`, `apex_icon`, `hide_readonly_on_add`). Third-party admin packages (`django-import-export`, `django-reversion`, etc.) ship their own templates and need targeted styling on top.

## Deployment

### Production environment variables

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | yes | Generate with `python -c 'import secrets; print(secrets.token_urlsafe(50))'` |
| `DATABASE_URL` | yes | `postgres://user:pass@host:5432/db` or `mssql://user:pass@host:1433/db` (see [SQL Server](#sql-server-microsoft-sql-server) below) |
| `ALLOWED_HOSTS` | yes | Comma-separated |
| `EMAIL_BACKEND` | recommended | `django.core.mail.backends.smtp.EmailBackend` for real email |
| `DEFAULT_FROM_EMAIL` | recommended | `noreply@yourdomain` |
| `DEBUG` | no | Defaults to `False` in `apex.settings.prod` |

### Deploy steps

```bash
DJANGO_SETTINGS_MODULE=apex.settings.prod
uv run python manage.py collectstatic --noinput
uv run python manage.py compilemessages
uv run python manage.py migrate
uv run gunicorn apex.wsgi:application --bind 0.0.0.0:8000
```

WhiteNoise serves static files in production — no nginx/CDN required for asset hosting.

### SQL Server (Microsoft SQL Server)

Apex supports Microsoft SQL Server 2017+ via Microsoft's official [`mssql-django`](https://github.com/microsoft/mssql-django) backend. Postgres remains the default — SQL Server is opt-in.

**1. Install the mssql extra:**

```bash
uv sync --extra mssql
```

This pulls `mssql-django` and `pyodbc`.

**2. Install Microsoft ODBC Driver 18** at the OS level:

macOS:

```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18 mssql-tools18
```

Ubuntu/Debian/RHEL/Windows: see Microsoft's [ODBC Driver 18 install guide](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

**3. Set `DATABASE_URL` with the `mssql://` scheme:**

```bash
DATABASE_URL=mssql://apex_user:password@sql.example.com:1433/apex
```

For self-signed certificates (typical for local docker or on-prem without a CA-signed cert), append `?trust_server_certificate=yes`:

```bash
DATABASE_URL=mssql://sa:Apex_Test_123!@localhost:1433/apex?trust_server_certificate=yes
```

To target an older ODBC driver (e.g. 17 instead of 18), append `?driver=ODBC+Driver+17+for+SQL+Server`. Both query params can be combined with `&`.

**4. Migrate as normal:**

```bash
DJANGO_SETTINGS_MODULE=apex.settings.prod \
  uv run python manage.py migrate
```

#### Local development against SQL Server

`apex/settings/mssql.py` is a development settings module pre-wired for a local SQL Server instance. Defaults match the SQL Server 2022 docker image command in the next section. Override via `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_DB`, `MSSQL_USER`, `MSSQL_PASSWORD`, `MSSQL_DRIVER` env vars.

```bash
DJANGO_SETTINGS_MODULE=apex.settings.mssql \
  uv run python manage.py migrate
```

#### Running SQL Server locally with Docker

```bash
docker run -d --name apex-mssql \
  -e ACCEPT_EULA=Y \
  -e MSSQL_SA_PASSWORD='Apex_Test_123!' \
  -p 1433:1433 \
  mcr.microsoft.com/mssql/server:2022-latest

docker exec -it apex-mssql /opt/mssql-tools18/bin/sqlcmd \
  -S localhost -U sa -P 'Apex_Test_123!' -C \
  -Q "CREATE DATABASE apex"
```

### One-host deployment

The project runs cleanly on:

- **Railway / Render / Fly.io** — set the env vars above, deploy via Dockerfile or buildpacks.
- **DigitalOcean / Hetzner droplet** — gunicorn + system nginx + Postgres + the env vars.
- **Heroku** — works with the Python buildpack, Postgres add-on, and `Procfile: web: gunicorn apex.wsgi`.

PDF rendering needs the cairo/pango system libs on the deploy host — most distro base images include them, but check first if your container is `alpine` or distroless.

## What's intentionally NOT included

- **Real-time WebSockets** — chat and notifications use HTMX polling. Add Django Channels later if a latency complaint actually surfaces.
- **External SMTP / verified senders** — `EMAIL_BACKEND` is the console backend in dev. Configure in prod settings.
- **Cloud file storage** — `FileField` writes to local `MEDIA_ROOT`. Wire `django-storages` for S3/GCS when ready.
- **Background jobs** — no Celery/RQ. Notifications fire synchronously inline with the request.
- **Customer-facing storefront** — the dashboard is staff-only. Public surfaces are limited to marketing pages, login, and shareable invoice tokens.

## Roadmap

The build is split into phases — see [`docs/superpowers/plans/2026-04-24-apex-parity-roadmap.md`](docs/superpowers/plans/2026-04-24-apex-parity-roadmap.md) for the original parity roadmap. Phase 8 expanded the template with Metronic-class surfaces (5 dashboard variants, projects, profiles, activity, billing, help center, blog, datatable, API docs, maps).

Recent additions are tracked in [`CHANGELOG.md`](CHANGELOG.md).

## License

Commercial. Included with the DashboardPack license. See `LICENSE` for details.

## Credit

Based on the [Apex Next.js Dashboard](https://apex-dashboard.pages.dev). Django port by DashboardPack.
