# Getting started

This guide walks you through setting up Apex Django locally in ~5 minutes,
then points at the deeper docs for everything else.

> **Buying or forking?** Read [`CUSTOMIZE.md`](../CUSTOMIZE.md) first — it
> covers the five things you'll change before deploying your own version.

## Prerequisites

- **Python 3.12 or 3.13** (NOT 3.14 — Django 5.1 incompatibility)
- **Node.js 20+**
- **`uv`** ([install](https://docs.astral.sh/uv/getting-started/installation/))
  or pip
- **WeasyPrint native libs** if you want PDF invoice rendering:
  - macOS: `brew install pango`
  - Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2`

Postgres + Redis are not needed for local dev — SQLite + the in-memory
channel layer cover everything (including realtime via Channels).

## Install

```bash
git clone <your-repo>
cd <project-dir>

uv sync --all-groups       # Python deps including dev/test
npm install                # Tailwind CLI + EasyMDE
npm run build              # Compile CSS once (or `npm run dev` to watch)
```

## Initialize the database

```bash
uv run python manage.py migrate
uv run python manage.py seed_demo
```

The seed creates a self-contained sandbox:

- **demo user** (`demo` / `ApexShowcase!2026`) — staff/admin, populated profile
- **15 random users** with realistic titles, locations, bios
- **3 organizations** (Apex Demo Co., Side Project, Acme Holdings) with the
  demo user as owner of each, plus 3 teammate memberships and 1 pending invite
  on the primary org
- **100 customers**, **5 product categories**, **25 products**
- **30 orders** with ~90 line items
- **15 invoices** spanning every status (draft / sent / paid / void)
- **6 projects** with milestones, tasks, team members
- **6 help-center categories** containing 19 articles
- **4 blog topics** with 9 posts
- **Pro subscription** on the demo account with two saved payment methods
- **~100 activity events** auto-emitted via signal hooks
- Demo files, calendar events, kanban cards, mail threads, chat history

## Run the dev server

```bash
uv run python manage.py runserver
```

Visit [http://localhost:8000/](http://localhost:8000/). The login form
pre-fills demo credentials in dev mode — click **Sign in** and you're
in. To turn that off: `DEMO_MODE = False` in `apex/settings/dev.py`.

For Tailwind hot-reload, run `npm run dev` in a second terminal.

## Run tests

```bash
uv run pytest                # unit tests (fast — under 90s)
uv run pytest -m e2e         # Playwright E2E (spawns Chromium)
./run-e2e.sh                 # both, sequentially
```

The unit suite covers ~1000 tests across every app, including the WS
consumers (`pytest-asyncio` + `WebsocketCommunicator`), API endpoints
(Django Ninja), org RBAC, login throttle, health checks, and form
widgets.

## What's in the box

This is a Metronic-class dashboard template — server-rendered Django
with Tailwind v4 + Alpine.js + HTMX, no SPA. Highlights:

- **5 dashboard variants** (Overview, Analytics, CRM, eCommerce, SaaS),
  each with theme-aware ApexCharts that re-render on dark-mode toggle
- **Productivity apps** — Mail (with reply chains, drafts, labels),
  Chat (per-recipient threads), Calendar (weekly + monthly views),
  Kanban (drag-and-drop), Files (folder tree + uploads), Projects
  (tasks + milestones + team), Activity (signal-fed timeline)
- **Commerce** — Customers, Orders, Invoices (with WeasyPrint PDF
  rendering), Products
- **Multi-tenant Organizations** — workspace switcher, 5-tier RBAC
  (owner/admin/billing/member/viewer), email invitations with TTL
- **Realtime via Channels** — per-user notification fan-out, presence
  pill in the header, `/realtime/` demo page; in-memory layer in dev,
  Redis in prod via `REDIS_URL`
- **API layer** — Django Ninja with auto-OpenAPI at `/api/v1/docs`,
  cursor pagination, bearer-token auth, HMAC-signed webhooks
- **Settings depth** — profile + appearance, password + 2FA + active
  sessions, API tokens with one-time reveal, webhook delivery log,
  GDPR-style data export ZIP, account deletion with 30-day grace
- **Marketing surfaces** — public landing pages, pricing, support,
  blog, help center, sitemap.xml, robots.txt, OG + Twitter cards
- **i18n** — English + Spanish bundled, header language picker,
  `gettext_lazy` across navigation
- **Demo + ops** — login auto-fill banner gated on `DEMO_MODE`,
  per-IP + per-username login throttle, `/__health/` JSON probe,
  optional Sentry SDK (opt-in via `SENTRY_DSN`)

## Where to go next

| If you want to… | Read |
|---|---|
| Customize for your brand | [`CUSTOMIZE.md`](../CUSTOMIZE.md) |
| Deploy to a Linux server (Daphne + nginx) | [`deploy/README.md`](../deploy/README.md) |
| Understand the architecture | [`CLAUDE.md`](../CLAUDE.md) |
| See every feature + screenshots | [`README.md`](../README.md) |
| Browse the API | start the dev server, visit `/api/v1/docs` |
| See the realtime layer in action | sign in, visit `/realtime/`, open in two tabs |

## Common gotchas

- **`No module named 'channels'`** — `uv sync` instead of `uv pip install`
  (we vendor Channels through the lockfile).
- **`HTTP/2 support not enabled`** at Daphne start — that's a benign
  notice; Daphne uses HTTP/1.1 to upstream and HTTP/2 is fine via nginx
  or Cloudflare in front.
- **WeasyPrint ImportError** — install the native libs (see
  Prerequisites). Tests skip the PDF render path automatically when
  WeasyPrint can't load.
- **Test DB stuck after a crash** — `rm db.sqlite3 && uv run python
  manage.py migrate && uv run python manage.py seed_demo`.
- **Stale CSS in browser after a `:root` change** — `npm run build`
  emits a fresh `static/css/app.css`; collectstatic + WhiteNoise's
  manifest hashing bust the browser cache automatically in prod.
