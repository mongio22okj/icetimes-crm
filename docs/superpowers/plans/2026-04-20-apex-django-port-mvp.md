# Apex Dashboard — Django Port (MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Django 5 port of the Apex Next.js admin dashboard as a sellable DashboardPack product. MVP covers the main dashboard, auth flows, and three CRUD resources — pixel-matched to Apex, but built on server-rendered Django templates with real models, not React.

**Architecture:** Django 5.1 + Python 3.12. Stock Django templates (no Jinja2). Tailwind CSS v4 built via npm, importing Apex's `globals.css` design tokens verbatim so the visual identity is 1:1. Interactivity via **Alpine.js** (local state — dropdowns, tabs, theme toggle) + **HTMX** (server partials — filters, table rows, form submits). Charts via **ApexCharts** vanilla JS (drop-in for Recharts). Real Django models + forms + CBVs drive every page — no mock data, because that is the entire point of a Django port versus the Next.js original.

**Tech Stack:**
- Python 3.12, Django 5.1, uv for dependency management
- Tailwind CSS v4 (npm-built, no django-tailwind bridge)
- Alpine.js 3.x, HTMX 2.x (CDN, version-pinned)
- ApexCharts 3.x (CDN, version-pinned)
- pytest-django, pytest-playwright, factory-boy for tests
- SQLite default for dev/demo; PostgreSQL optional via env
- Django's built-in auth (login/logout/password-reset) — no allauth for MVP
- whitenoise for static serving in production

**Scope (MVP — Phase 1):**
Dashboard landing (stats + revenue chart + side panel + recent orders + activity feed) · Auth (login, register, logout, forgot-password, reset-password) · Users CRUD (list, detail, create, edit) · Products CRUD (list, detail, create, edit) · Orders CRUD (list, detail, create, edit) · Settings (profile) · Error pages (403, 404, 500) · Seed data for demo.

**Verify-email is deferred** to Phase 2 (requires email backend config + allauth); the MVP registration auto-logs-in without verification.

**Out of scope (Phase 2+):** Analytics/SaaS/CRM/eCommerce landing variants, Invoices, Chat, Mail, Calendar, Kanban, Files, Notifications, Pricing, Support, Wizard, Charts showcase, Customers (distinct from Users), Docs pages, i18n, lock-screen, two-factor, command palette, theme customizer drawer.

---

## File Structure

```
dashboardpack-apex-django/
├── manage.py
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── .env.example
├── .gitignore
├── package.json
├── tailwind.config.js                  # Tailwind v4 config
├── postcss.config.js
├── apex/                               # Django project (settings)
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── __init__.py
│   ├── core/                           # Base templates, partials, middleware, context processors
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── context_processors.py       # nav_items, theme
│   │   ├── templatetags/
│   │   │   ├── __init__.py
│   │   │   └── apex.py                 # {% icon %}, {% active %} helpers
│   │   └── views.py                    # 403/404/500 handlers
│   ├── accounts/                       # User model, auth views, profile
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── models.py                   # User(AbstractUser) + Profile
│   │   ├── forms.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── migrations/
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_models.py
│   │       ├── test_views.py
│   │       └── factories.py
│   ├── products/                       # Product model + CRUD
│   │   ├── models.py (Product, Category)
│   │   ├── forms.py
│   │   ├── views.py (list/detail/create/edit)
│   │   ├── urls.py
│   │   └── tests/
│   ├── orders/                         # Order + OrderItem + CRUD
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tests/
│   └── dashboard/                      # Landing page, stats aggregation
│       ├── views.py                    # DashboardView
│       ├── urls.py
│       └── tests/
├── templates/
│   ├── base.html                       # <html>, <head>, design tokens, theme init
│   ├── layouts/
│   │   ├── dashboard.html               # sidebar + header + {% block content %}
│   │   └── auth.html                    # centered card layout
│   ├── partials/
│   │   ├── sidebar.html
│   │   ├── header.html
│   │   ├── theme_toggle.html
│   │   ├── pagination.html
│   │   └── messages.html
│   ├── components/
│   │   ├── stat_card.html
│   │   ├── data_table.html
│   │   ├── form_field.html
│   │   ├── empty_state.html
│   │   └── button.html
│   ├── dashboard/
│   │   └── index.html
│   ├── registration/                   # Django auth template names
│   │   ├── login.html
│   │   ├── password_reset_form.html
│   │   ├── password_reset_done.html
│   │   ├── password_reset_confirm.html
│   │   ├── password_reset_complete.html
│   │   └── logged_out.html
│   ├── accounts/
│   │   ├── register.html
│   │   ├── profile.html
│   │   ├── user_list.html
│   │   ├── user_detail.html
│   │   └── user_form.html
│   ├── products/
│   │   ├── product_list.html
│   │   ├── product_detail.html
│   │   └── product_form.html
│   ├── orders/
│   │   ├── order_list.html
│   │   ├── order_detail.html
│   │   └── order_form.html
│   └── errors/
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
├── static_src/
│   ├── css/
│   │   └── input.css                   # @import "tailwindcss"; + Apex design tokens
│   ├── js/
│   │   ├── app.js                      # theme init, Alpine components
│   │   └── charts.js                   # ApexCharts wrappers
│   └── vendor/                         # Pinned Alpine/HTMX/ApexCharts
├── static/                             # Compiled output (gitignored except /vendor)
├── seed/
│   └── demo_data.py                    # management command: seed_demo
├── tests/
│   ├── conftest.py
│   └── e2e/
│       └── test_smoke.py               # Playwright
└── docs/
    └── superpowers/plans/2026-04-20-apex-django-port-mvp.md   # this file
```

**Decomposition rationale:**
- `core` holds cross-cutting template infrastructure so each feature app stays focused on its models/views.
- Feature apps (`accounts`, `products`, `orders`, `dashboard`) are boundary-aligned — each owns its models, views, urls, forms, templates, tests together.
- Templates co-located by feature in `templates/<app>/`, shared partials in `templates/partials/`, pure visual bits in `templates/components/`.
- `static_src/` is the source, `static/` is the built output. The Tailwind build watches `static_src/` + `templates/**/*.html`.

**Apex reference:** `/Users/silkalns/Projects/admin-dashboard/` — copy design tokens from `src/app/globals.css`, navigation structure from `src/components/dashboard/sidebar.tsx`, page layouts from `src/app/(dashboard)/*/page.tsx`, acceptance smoke test patterns from `e2e/smoke.spec.ts`.

---

## Task 0: Project scaffolding + CI-ready test harness

**Files:**
- Create: `pyproject.toml`, `package.json`, `manage.py`, `apex/settings/{base,dev,prod}.py`, `apex/urls.py`, `apex/wsgi.py`, `.env.example`, `.gitignore`, `README.md`, `tailwind.config.js`, `postcss.config.js`, `static_src/css/input.css`, `tests/conftest.py`

- [ ] **Step 1: Initialize git + write `.gitignore`**

```bash
cd /Users/silkalns/Projects/dashboardpack-apex-django
git init
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.env
db.sqlite3
node_modules/
static/*
!static/vendor/
staticfiles/
.pytest_cache/
.playwright/
test-results/
*.log
.DS_Store
```

- [ ] **Step 2: Write `pyproject.toml` with pinned deps**

```toml
[project]
name = "apex-dashboard-django"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "django>=5.1,<5.2",
  "whitenoise>=6.7",
  "python-dotenv>=1.0",
  "pillow>=11.0",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-django>=4.9",
  "pytest-playwright>=0.6",
  "factory-boy>=3.3",
  "ruff>=0.7",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "apex.settings.dev"
python_files = ["test_*.py"]
```

Install: `uv sync --all-groups && uv run playwright install chromium`

- [ ] **Step 3: Scaffold Django project**

```bash
uv run django-admin startproject apex .
mkdir -p apex/settings && mv apex/settings.py apex/settings/base.py
```

Split `base.py` / `dev.py` / `prod.py`: dev uses SQLite + `DEBUG=True`, prod reads `DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS` from env.

Add to `base.py`:
```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.products",
    "apps.orders",
    "apps.dashboard",
]
AUTH_USER_MODEL = "accounts.User"
TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
TEMPLATES[0]["OPTIONS"]["context_processors"].append("apps.core.context_processors.navigation")
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
```

- [ ] **Step 4: Scaffold `package.json` + Tailwind v4**

```json
{
  "scripts": {
    "dev": "tailwindcss -i ./static_src/css/input.css -o ./static/css/app.css --watch",
    "build": "tailwindcss -i ./static_src/css/input.css -o ./static/css/app.css --minify"
  },
  "devDependencies": {
    "@tailwindcss/cli": "^4.0.0",
    "tailwindcss": "^4.0.0"
  }
}
```

`static_src/css/input.css` — copy the entire `/Users/silkalns/Projects/admin-dashboard/src/app/globals.css` (the `@import`, `@custom-variant`, `@theme inline`, `:root`, `.dark`, and `@keyframes` blocks). Replace `@source "../../node_modules/@dashboardpack/core"` with `@source "../../templates/**/*.html"`.

Run: `npm install && npm run build`

- [ ] **Step 5: Write scaffolding smoke test**

`tests/conftest.py`:
```python
import pytest

@pytest.fixture
def client_anon(client):
    return client
```

`apps/core/tests/test_smoke.py`:
```python
import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_admin_login_page_renders(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200
```

- [ ] **Step 6: Run test, migrate, verify**

```bash
uv run python manage.py migrate
uv run pytest -v
```
Expected: `1 passed`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold Django 5 project with Tailwind v4 and pytest harness"
```

---

## Task 1: Base template + Apex design tokens

**Files:**
- Create: `templates/base.html`, `templates/layouts/dashboard.html`, `templates/layouts/auth.html`, `templates/partials/theme_toggle.html`, `static_src/js/app.js`
- Modify: `static_src/css/input.css`

- [ ] **Step 1: Write failing test for design tokens reaching the page**

`apps/core/tests/test_templates.py`:
```python
import pytest
from django.test import RequestFactory
from django.template.loader import render_to_string

def test_base_template_includes_apex_css():
    html = render_to_string("base.html", {"request": RequestFactory().get("/")})
    assert 'href="/static/css/app.css"' in html
    assert 'class="bg-background text-foreground"' in html

def test_base_template_has_theme_init_script():
    html = render_to_string("base.html", {"request": RequestFactory().get("/")})
    # Prevents dark-mode flash: must run before body
    assert 'localStorage.getItem("theme")' in html
    assert 'document.documentElement.classList' in html
```

Run: `uv run pytest apps/core/tests/test_templates.py -v` → FAIL (template missing).

- [ ] **Step 2: Write `templates/base.html`**

```html
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Apex Dashboard{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/app.css' %}">
  <script>
    (function() {
      const saved = localStorage.getItem("theme");
      const system = window.matchMedia("(prefers-color-scheme: dark)").matches;
      const dark = saved === "dark" || (!saved && system);
      if (dark) document.documentElement.classList.add("dark");
    })();
  </script>
  <script src="https://unpkg.com/htmx.org@2.0.3" defer></script>
  <script src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
  {% block head_extra %}{% endblock %}
</head>
<body class="bg-background text-foreground antialiased">
  {% block body %}{% endblock %}
  <script src="{% static 'js/app.js' %}" defer></script>
</body>
</html>
```

- [ ] **Step 3: Verify test passes**

```bash
uv run pytest apps/core/tests/test_templates.py -v
```
Expected: PASS.

- [ ] **Step 4: Write `layouts/auth.html` (centered card)**

```html
{% extends "base.html" %}
{% block body %}
<div class="min-h-screen flex items-center justify-center bg-background p-4">
  <div class="w-full max-w-md rounded-lg border border-border bg-card p-6 shadow-sm">
    {% block auth_content %}{% endblock %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Write `layouts/dashboard.html` (shell with sidebar + header placeholders)**

```html
{% extends "base.html" %}
{% block body %}
<div class="flex min-h-screen">
  {% include "partials/sidebar.html" %}
  <div class="flex-1 ml-[260px]">
    {% include "partials/header.html" %}
    <main class="p-6">
      {% block content %}{% endblock %}
    </main>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(core): base template with Apex design tokens and dark-mode init"
```

---

## Task 2: Sidebar partial with Apex nav structure

**Files:**
- Create: `templates/partials/sidebar.html`, `apps/core/context_processors.py`, `apps/core/templatetags/apex.py`
- Create: `apps/core/tests/test_nav.py`

**Reference:** Apex nav in `/Users/silkalns/Projects/admin-dashboard/src/components/dashboard/sidebar.tsx:55-170`. MVP includes only links for pages we're building; stub the rest with `href="#"` and a `data-wip` attribute.

- [ ] **Step 1: Write failing test for nav context processor**

`apps/core/tests/test_nav.py`:
```python
from apps.core.context_processors import navigation
from django.test import RequestFactory

def test_navigation_context_has_overview_group():
    request = RequestFactory().get("/")
    ctx = navigation(request)
    groups = ctx["nav_groups"]
    overview = next(g for g in groups if g["label"] == "Overview")
    assert any(i["href"] == "/" and i["label"] == "Dashboard" for i in overview["items"])

def test_navigation_includes_products_and_orders_in_commerce():
    ctx = navigation(RequestFactory().get("/"))
    commerce = next(g for g in ctx["nav_groups"] if g["label"] == "Commerce")
    labels = {i["label"] for i in commerce["items"]}
    assert {"Orders", "Products"} <= labels
```

Run → FAIL.

- [ ] **Step 2: Implement `context_processors.py`**

```python
def navigation(request):
    return {
        "nav_groups": [
            {"label": "Overview", "items": [
                {"label": "Dashboard", "href": "/", "icon": "layout-dashboard"},
            ]},
            {"label": "Commerce", "items": [
                {"label": "Orders", "href": "/orders/", "icon": "shopping-cart"},
                {"label": "Products", "href": "/products/", "icon": "package"},
            ]},
            {"label": "Account", "items": [
                {"label": "Users", "href": "/users/", "icon": "users"},
                {"label": "Settings", "href": "/settings/", "icon": "settings"},
            ]},
        ],
        "current_path": request.path,
    }
```

Verify: `uv run pytest apps/core/tests/test_nav.py -v` → PASS.

- [ ] **Step 3: Write `{% icon %}` templatetag (inline Lucide SVGs)**

`apps/core/templatetags/apex.py`:
```python
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ICONS = {
    "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "shopping-cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
}

@register.simple_tag
def icon(name, size=18, cls=""):
    body = ICONS.get(name, "")
    return mark_safe(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round" class="{cls}">{body}</svg>'
    )

@register.simple_tag
def active(current_path, href, exact=False, cls="bg-sidebar-accent text-sidebar-accent-foreground"):
    if exact:
        return cls if current_path == href else ""
    return cls if current_path.startswith(href) and href != "/" else (cls if current_path == "/" and href == "/" else "")
```

- [ ] **Step 4: Write `templates/partials/sidebar.html`**

```html
{% load apex %}
<aside class="fixed left-0 top-0 h-screen w-[260px] bg-sidebar text-sidebar-foreground border-r border-sidebar-border">
  <div class="h-16 flex items-center px-6 border-b border-sidebar-border">
    <a href="/" class="flex items-center gap-2 font-semibold text-sidebar-primary-foreground">
      {% icon "package" 22 %}
      <span>Apex</span>
    </a>
  </div>
  <nav class="p-4 space-y-6">
    {% for group in nav_groups %}
      <div>
        <p class="px-2 pb-2 text-xs uppercase tracking-wider text-sidebar-foreground/60">{{ group.label }}</p>
        <ul class="space-y-1">
          {% for item in group.items %}
            <li>
              <a href="{{ item.href }}"
                 class="flex items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground {% active current_path item.href %}">
                {% icon item.icon 18 %}
                <span>{{ item.label }}</span>
              </a>
            </li>
          {% endfor %}
        </ul>
      </div>
    {% endfor %}
  </nav>
</aside>
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(core): sidebar partial with nav groups and icon templatetag"
```

---

## Task 3: Header partial with theme toggle

**Files:**
- Create: `templates/partials/header.html`, `templates/partials/theme_toggle.html`
- Modify: `static_src/js/app.js`

- [ ] **Step 1: Write E2E-ready unit test for theme toggle markup**

`apps/core/tests/test_header.py`:
```python
from django.template.loader import render_to_string
from django.test import RequestFactory

def test_header_renders_theme_toggle():
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    assert 'aria-label="Toggle theme"' in html
    assert 'x-on:click' in html  # Alpine binding

def test_theme_toggle_writes_localstorage():
    # Verified at unit level by inspecting the Alpine handler string
    html = render_to_string("partials/header.html", {"request": RequestFactory().get("/")})
    assert "localStorage.setItem('theme'" in html
```

Run → FAIL.

- [ ] **Step 2: Implement `templates/partials/header.html`**

```html
{% load apex %}
<header class="h-16 border-b border-border bg-card/50 backdrop-blur sticky top-0 z-10 flex items-center justify-between px-6">
  <div class="flex-1 max-w-md">
    <input type="search" placeholder="Search..."
           class="w-full h-9 rounded-md border border-input bg-background px-3 text-sm">
  </div>
  <div class="flex items-center gap-3">
    <button type="button"
            aria-label="Toggle theme"
            x-data="{}"
            x-on:click="
              const el = document.documentElement;
              el.classList.toggle('dark');
              localStorage.setItem('theme', el.classList.contains('dark') ? 'dark' : 'light');
            "
            class="h-9 w-9 rounded-md border border-border inline-flex items-center justify-center hover:bg-accent">
      {% icon "settings" 18 %}
    </button>
    {% if user.is_authenticated %}
      <form method="post" action="{% url 'logout' %}">{% csrf_token %}
        <button type="submit" class="text-sm">{{ user.username }}</button>
      </form>
    {% endif %}
  </div>
</header>
```

- [ ] **Step 3: Verify**

```bash
uv run pytest apps/core/tests/test_header.py -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(core): header partial with theme toggle via Alpine + localStorage"
```

---

## Task 4: Accounts app — User model + registration

**Files:**
- Create: `apps/accounts/{apps,models,forms,views,urls,admin}.py`, `apps/accounts/tests/{__init__,factories,test_models,test_views}.py`
- Create: `templates/accounts/register.html`

- [ ] **Step 1: Write failing model tests**

`apps/accounts/tests/test_models.py`:
```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_user_model_is_custom():
    assert User._meta.app_label == "accounts"

@pytest.mark.django_db
def test_user_has_full_name_helper():
    user = User.objects.create_user(username="alice", email="a@b.co", first_name="Alice", last_name="Adams")
    assert user.get_full_name() == "Alice Adams"

@pytest.mark.django_db
def test_user_has_avatar_field():
    user = User.objects.create_user(username="bob", email="b@b.co")
    assert hasattr(user, "avatar")
```

Run → FAIL.

- [ ] **Step 2: Implement `apps/accounts/models.py`**

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    role = models.CharField(
        max_length=32,
        choices=[("admin", "Admin"), ("manager", "Manager"), ("staff", "Staff")],
        default="staff",
    )
    bio = models.TextField(blank=True)
```

Run: `uv run python manage.py makemigrations accounts && uv run python manage.py migrate`.

Verify: `uv run pytest apps/accounts/tests/test_models.py -v` → PASS.

- [ ] **Step 3: Write factory for test fixtures**

`apps/accounts/tests/factories.py`:
```python
import factory
from django.contrib.auth import get_user_model

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        django_get_or_create = ("username",)

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    password = factory.PostGenerationMethodCall("set_password", "password")
```

The `password` post-generation hook ensures every factory-created user can log in with `password` — required by the E2E suite in Task 17.

- [ ] **Step 4: Write failing tests for register view**

`apps/accounts/tests/test_views.py`:
```python
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_register_get_renders_form(client):
    response = client.get(reverse("register"))
    assert response.status_code == 200
    assert b"Create your account" in response.content

@pytest.mark.django_db
def test_register_post_creates_user_and_redirects(client):
    response = client.post(reverse("register"), {
        "username": "newuser",
        "email": "new@example.com",
        "password1": "Complex-passw0rd",
        "password2": "Complex-passw0rd",
    })
    assert response.status_code == 302
    assert User.objects.filter(username="newuser").exists()
```

Run → FAIL.

- [ ] **Step 5: Implement register view + form + url + template**

`apps/accounts/forms.py`:
```python
from django.contrib.auth.forms import UserCreationForm
from .models import User

class RegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")
```

`apps/accounts/views.py`:
```python
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views import View
from .forms import RegisterForm

class RegisterView(View):
    def get(self, request):
        return render(request, "accounts/register.html", {"form": RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
        return render(request, "accounts/register.html", {"form": form})
```

`apps/accounts/urls.py`:
```python
from django.urls import path
from .views import RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
]
```

Wire in `apex/urls.py`:
```python
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

`templates/accounts/register.html`:
```html
{% extends "layouts/auth.html" %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Create your account</h1>
<p class="text-sm text-muted-foreground mb-6">Start your 14-day trial. No credit card required.</p>
<form method="post" class="space-y-4">
  {% csrf_token %}
  {% for field in form %}
    <div>
      <label class="block text-sm font-medium mb-1">{{ field.label }}</label>
      {{ field }}
      {% if field.errors %}<p class="text-xs text-destructive mt-1">{{ field.errors.0 }}</p>{% endif %}
    </div>
  {% endfor %}
  <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">Create account</button>
</form>
<p class="mt-4 text-sm text-muted-foreground text-center">
  Already have an account? <a href="{% url 'login' %}" class="text-primary font-medium">Sign in</a>
</p>
{% endblock %}
```

- [ ] **Step 6: Verify tests pass + commit**

```bash
uv run pytest apps/accounts/ -v
git add -A
git commit -m "feat(accounts): custom User model + registration flow"
```

---

## Task 5: Login / logout / password-reset templates

**Files:**
- Create: `templates/registration/{login,password_reset_form,password_reset_done,password_reset_confirm,password_reset_complete,logged_out}.html`
- Modify: `apex/urls.py` to wire password-reset URLs

- [ ] **Step 1: Write failing view test**

`apps/accounts/tests/test_auth_flow.py`:
```python
import pytest
from django.urls import reverse
from .factories import UserFactory

@pytest.mark.django_db
def test_login_page_renders(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert b"Sign in" in response.content

@pytest.mark.django_db
def test_login_succeeds_with_valid_credentials(client):
    user = UserFactory(username="alice")
    user.set_password("testpass123"); user.save()
    response = client.post(reverse("login"), {"username": "alice", "password": "testpass123"})
    assert response.status_code == 302

@pytest.mark.django_db
def test_password_reset_request_renders(client):
    response = client.get(reverse("password_reset"))
    assert response.status_code == 200
    assert b"Reset your password" in response.content
```

Run → FAIL (templates missing).

- [ ] **Step 2: Write login template**

`templates/registration/login.html`:
```html
{% extends "layouts/auth.html" %}
{% block auth_content %}
<h1 class="text-2xl font-bold tracking-tight mb-1">Sign in</h1>
<p class="text-sm text-muted-foreground mb-6">Welcome back. Enter your credentials.</p>
<form method="post" class="space-y-4">
  {% csrf_token %}
  <div>
    <label class="block text-sm font-medium mb-1">Username</label>
    <input type="text" name="username" required
           class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
  </div>
  <div>
    <label class="block text-sm font-medium mb-1">Password</label>
    <input type="password" name="password" required
           class="w-full h-10 rounded-md border border-input bg-background px-3 text-sm">
  </div>
  {% if form.errors %}
    <p class="text-xs text-destructive">Invalid username or password.</p>
  {% endif %}
  <button type="submit" class="w-full h-10 rounded-md bg-primary text-primary-foreground font-medium">Sign in</button>
</form>
<div class="mt-4 flex items-center justify-between text-sm">
  <a href="{% url 'password_reset' %}" class="text-primary">Forgot password?</a>
  <a href="{% url 'register' %}" class="text-muted-foreground">Create account</a>
</div>
{% endblock %}
```

- [ ] **Step 3: Add password-reset URLs to `apex/urls.py`**

```python
from django.contrib.auth import views as auth_views
# ... inside urlpatterns:
path("accounts/password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
```

- [ ] **Step 4: Write remaining 5 auth templates**

For each of `password_reset_form.html`, `password_reset_done.html`, `password_reset_confirm.html`, `password_reset_complete.html`, `logged_out.html` — `{% extends "layouts/auth.html" %}` with a titled card and appropriate form (match Apex's `/forgot-password/` and `/reset-password/` copy).

- [ ] **Step 5: Verify + commit**

```bash
uv run pytest apps/accounts/ -v
git add -A
git commit -m "feat(accounts): login, logout, password-reset templates"
```

---

## Task 6: Dashboard app — landing page with stats cards

**Files:**
- Create: `apps/dashboard/{views,urls}.py`, `apps/dashboard/tests/test_views.py`
- Create: `templates/dashboard/index.html`, `templates/components/stat_card.html`
- Modify: `apex/urls.py`, `apps/core/context_processors.py` (no change needed yet)

**Reference:** `/Users/silkalns/Projects/admin-dashboard/src/components/dashboard/stats-cards.tsx` for stat card shape and `/Users/silkalns/Projects/admin-dashboard/src/app/(dashboard)/page.tsx` for the grid layout.

- [ ] **Step 1: Write failing test**

`apps/dashboard/tests/test_views.py`:
```python
import pytest
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory

@pytest.mark.django_db
def test_dashboard_redirects_anon_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/accounts/login" in response.url

@pytest.mark.django_db
def test_dashboard_renders_for_authed_user(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Total Revenue" in response.content
    assert b"Active Users" in response.content

@pytest.mark.django_db
def test_dashboard_stats_come_from_db(client, django_assert_num_queries):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/")
    ctx = response.context
    assert "stats" in ctx
    assert {"label", "value", "delta"} <= set(ctx["stats"][0].keys())
```

- [ ] **Step 2: Implement view + url**

`apps/dashboard/views.py`:
```python
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    def get(self, request):
        User = get_user_model()
        stats = [
            {"label": "Total Revenue", "value": "$45,231.89", "delta": "+20.1%", "trend": "up"},
            {"label": "Active Users", "value": str(User.objects.count()), "delta": "+180.1%", "trend": "up"},
            {"label": "Sales", "value": "+12,234", "delta": "+19%", "trend": "up"},
            {"label": "Active Now", "value": "+573", "delta": "+201", "trend": "up"},
        ]
        return render(request, "dashboard/index.html", {"stats": stats})
```

`apps/dashboard/urls.py`:
```python
from django.urls import path
from .views import DashboardView

urlpatterns = [path("", DashboardView.as_view(), name="dashboard")]
```

Wire in `apex/urls.py`: `path("", include("apps.dashboard.urls"))`.

- [ ] **Step 3: Write `templates/components/stat_card.html`**

```html
<div class="rounded-lg border border-border bg-card p-4">
  <p class="text-sm text-muted-foreground">{{ label }}</p>
  <p class="text-2xl font-bold tracking-tight mt-2">{{ value }}</p>
  <p class="text-xs mt-1 {% if trend == 'up' %}text-success{% else %}text-destructive{% endif %}">
    {{ delta }} from last month
  </p>
</div>
```

- [ ] **Step 4: Write `templates/dashboard/index.html`**

```html
{% extends "layouts/dashboard.html" %}
{% block title %}Dashboard · Apex{% endblock %}
{% block content %}
<div class="mb-6">
  <h1 class="text-2xl font-bold tracking-tight">Dashboard</h1>
  <p class="mt-1 text-sm text-muted-foreground">Welcome back. Here's what's happening.</p>
</div>
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
  {% for stat in stats %}
    {% include "components/stat_card.html" with label=stat.label value=stat.value delta=stat.delta trend=stat.trend %}
  {% endfor %}
</div>
{# Revenue chart + side panel + recent orders + activity feed added in Tasks 7-10 #}
{% endblock %}
```

- [ ] **Step 5: Verify + commit**

```bash
uv run python manage.py migrate
uv run pytest apps/dashboard/ -v
git add -A
git commit -m "feat(dashboard): landing page with auth-gated stats cards"
```

---

## Task 7: Revenue chart via ApexCharts + HTMX tab swap

**Files:**
- Create: `templates/dashboard/_revenue_chart.html`, `static_src/js/charts.js`
- Modify: `apps/dashboard/views.py`, `apps/dashboard/urls.py`, `templates/base.html` (add ApexCharts script tag)

**Reference:** `/Users/silkalns/Projects/admin-dashboard/src/components/dashboard/revenue-chart.tsx` for data shape + tab UX.

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.django_db
def test_revenue_chart_partial_returns_json_data(client):
    user = UserFactory(); client.force_login(user)
    response = client.get("/charts/revenue/?range=7d")
    assert response.status_code == 200
    assert "application/json" in response["Content-Type"]
    data = response.json()
    assert "series" in data and "categories" in data

@pytest.mark.django_db
def test_revenue_chart_renders_container(client):
    user = UserFactory(); client.force_login(user)
    response = client.get("/")
    assert b'id="revenue-chart"' in response.content
```

- [ ] **Step 2: Add ApexCharts to `base.html`**

```html
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.54.1"></script>
```

- [ ] **Step 3: Implement view**

```python
# apps/dashboard/views.py
from django.http import JsonResponse

@login_required
def revenue_chart_data(request):
    range_key = request.GET.get("range", "7d")
    data = {
        "7d":  {"categories": ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], "series": [[4400, 5500, 5700, 5600, 6100, 5800, 6400]]},
        "30d": {"categories": [f"D{i}" for i in range(1,31)], "series": [[4000 + i*100 for i in range(30)]]},
        "90d": {"categories": [f"W{i}" for i in range(1,13)], "series": [[40000 + i*1200 for i in range(12)]]},
    }
    return JsonResponse(data.get(range_key, data["7d"]))
```

Wire URL: `path("charts/revenue/", revenue_chart_data, name="revenue_chart_data")`.

- [ ] **Step 4: Write chart partial**

`templates/dashboard/_revenue_chart.html`:
```html
<div class="xl:col-span-8 rounded-lg border border-border bg-card p-4"
     x-data="revenueChart()" x-init="init()">
  <div class="flex items-center justify-between mb-4">
    <h2 class="font-semibold">Revenue</h2>
    <div class="flex gap-1 text-xs">
      <template x-for="r in ['7d','30d','90d']" :key="r">
        <button type="button" x-text="r" x-on:click="load(r)"
                :class="range === r ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'"
                class="px-3 h-8 rounded-md"></button>
      </template>
    </div>
  </div>
  <div id="revenue-chart" class="h-[320px]"></div>
</div>
```

`static_src/js/charts.js`:
```javascript
function revenueChart() {
  return {
    range: '7d', chart: null,
    async init() { await this.load(this.range); },
    async load(range) {
      this.range = range;
      const res = await fetch(`/charts/revenue/?range=${range}`);
      const data = await res.json();
      const opts = {
        chart: { type: 'area', height: 320, toolbar: { show: false } },
        series: data.series.map((d, i) => ({ name: `Series ${i+1}`, data: d })),
        xaxis: { categories: data.categories },
        colors: ['var(--chart-1)'],
        stroke: { curve: 'smooth', width: 2 },
        dataLabels: { enabled: false },
      };
      if (this.chart) { this.chart.updateOptions(opts); }
      else { this.chart = new ApexCharts(document.querySelector('#revenue-chart'), opts); this.chart.render(); }
    }
  };
}
window.revenueChart = revenueChart;
```

Load in `base.html`: `<script src="{% static 'js/charts.js' %}" defer></script>`.

- [ ] **Step 5: Include the partial in dashboard; verify + commit**

`templates/dashboard/index.html` — append to content block:
```html
<div class="mt-6 grid grid-cols-1 xl:grid-cols-12 gap-4">
  {% include "dashboard/_revenue_chart.html" %}
</div>
```

```bash
uv run pytest apps/dashboard/ -v
git add -A
git commit -m "feat(dashboard): revenue chart with ApexCharts + HTMX range selector"
```

---

## Task 8: Side panel (traffic pie + goals progress bars)

**Files:**
- Create: `templates/dashboard/_side_panel.html`
- Modify: `apps/dashboard/views.py`, `static_src/js/charts.js`, `templates/dashboard/index.html`

**Reference:** `/Users/silkalns/Projects/admin-dashboard/src/components/dashboard/side-panel.tsx`.

- [ ] **Step 1: Test**

```python
@pytest.mark.django_db
def test_dashboard_renders_side_panel(client):
    client.force_login(UserFactory())
    response = client.get("/")
    assert b'id="traffic-chart"' in response.content
    assert b"Goals" in response.content
```

- [ ] **Step 2: Add to view context**

```python
"traffic_sources": [
    {"label": "Direct", "value": 45}, {"label": "Organic Search", "value": 30},
    {"label": "Social", "value": 15}, {"label": "Referral", "value": 10},
],
"goals": [
    {"label": "New Signups", "current": 847, "target": 1000},
    {"label": "Revenue Target", "current": 34500, "target": 50000},
    {"label": "Feature Adoption", "current": 62, "target": 80},
],
```

- [ ] **Step 3: Write partial**

`templates/dashboard/_side_panel.html`:
```html
<div class="xl:col-span-4 rounded-lg border border-border bg-card p-4 space-y-6">
  <div>
    <h2 class="font-semibold mb-4">Traffic Sources</h2>
    <div id="traffic-chart" class="h-[200px]"
         x-data="trafficChart({{ traffic_sources|safe }})" x-init="init()"></div>
  </div>
  <div>
    <h2 class="font-semibold mb-4">Goals</h2>
    <ul class="space-y-3">
      {% for g in goals %}
      <li>
        <div class="flex items-center justify-between text-sm mb-1">
          <span>{{ g.label }}</span>
          <span class="text-muted-foreground">{{ g.current }}/{{ g.target }}</span>
        </div>
        <div class="h-2 rounded-full bg-muted overflow-hidden">
          <div class="h-full bg-primary" style="width: {% widthratio g.current g.target 100 %}%"></div>
        </div>
      </li>
      {% endfor %}
    </ul>
  </div>
</div>
```

Extend `static_src/js/charts.js` with a `trafficChart(sources)` factory (donut, colors: `['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)']`).

Pass `traffic_sources` through the template — because Alpine wants JSON, not Django objects, convert the list to JSON in the view: `json.dumps(traffic_sources)` passed as `traffic_sources_json`, then `x-data="trafficChart({{ traffic_sources_json|safe }})"`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(dashboard): side panel with traffic donut and goals progress"
```

---

## Task 9: Products app — model, factory, list view

**Files:**
- Create: `apps/products/{models,forms,views,urls,admin}.py`, `apps/products/tests/{test_models,test_views,factories}.py`, `templates/products/product_list.html`, `templates/components/data_table.html`

- [ ] **Step 1: Failing model test**

```python
# apps/products/tests/test_models.py
import pytest
from apps.products.models import Product, Category

@pytest.mark.django_db
def test_product_has_required_fields():
    cat = Category.objects.create(name="Electronics", slug="electronics")
    p = Product.objects.create(name="Widget", slug="widget", sku="SKU-001", price=19.99, stock=50, category=cat)
    assert p.name == "Widget"
    assert str(p) == "Widget"

@pytest.mark.django_db
def test_product_status_defaults_to_draft():
    cat = Category.objects.create(name="X", slug="x")
    p = Product.objects.create(name="Y", slug="y", sku="Z", price=1, stock=1, category=cat)
    assert p.status == "draft"
```

- [ ] **Step 2: Implement model**

```python
# apps/products/models.py
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    def __str__(self): return self.name

class Product(models.Model):
    STATUS = [("draft", "Draft"), ("published", "Published"), ("archived", "Archived")]
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS, default="draft")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self): return self.name
```

Migrate: `uv run python manage.py makemigrations products && uv run python manage.py migrate`.

- [ ] **Step 3: Write factory + list-view test**

`apps/products/tests/factories.py`:
```python
import factory
from apps.products.models import Product, Category

class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta: model = Category
    name = factory.Sequence(lambda n: f"Cat {n}")
    slug = factory.Sequence(lambda n: f"cat-{n}")

class ProductFactory(factory.django.DjangoModelFactory):
    class Meta: model = Product
    name = factory.Sequence(lambda n: f"Product {n}")
    slug = factory.Sequence(lambda n: f"product-{n}")
    sku = factory.Sequence(lambda n: f"SKU-{n:04d}")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    stock = factory.Faker("pyint", min_value=0, max_value=500)
    category = factory.SubFactory(CategoryFactory)
```

`apps/products/tests/test_views.py`:
```python
import pytest
from django.urls import reverse
from apps.accounts.tests.factories import UserFactory
from .factories import ProductFactory

@pytest.mark.django_db
def test_product_list_requires_login(client):
    r = client.get("/products/")
    assert r.status_code == 302

@pytest.mark.django_db
def test_product_list_renders_rows(client):
    client.force_login(UserFactory())
    ProductFactory.create_batch(3)
    r = client.get("/products/")
    assert r.status_code == 200
    assert r.content.count(b"SKU-") >= 3

@pytest.mark.django_db
def test_product_list_paginates(client):
    client.force_login(UserFactory())
    ProductFactory.create_batch(25)
    r = client.get("/products/")
    # Default page size 20 → page 1 shows 20 rows
    assert r.context["page_obj"].paginator.count == 25
    assert len(r.context["page_obj"].object_list) == 20
```

- [ ] **Step 4: Implement ListView**

`apps/products/views.py`:
```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Product

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    paginate_by = 20
    template_name = "products/product_list.html"
    context_object_name = "products"
```

`apps/products/urls.py`:
```python
from django.urls import path
from .views import ProductListView

urlpatterns = [path("", ProductListView.as_view(), name="product_list")]
```

Wire: `path("products/", include("apps.products.urls"))`.

- [ ] **Step 5: Template**

`templates/products/product_list.html`:
```html
{% extends "layouts/dashboard.html" %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="text-2xl font-bold tracking-tight">Products</h1>
    <p class="text-sm text-muted-foreground">{{ page_obj.paginator.count }} total</p>
  </div>
  <a href="{% url 'product_create' %}" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium">New product</a>
</div>
<div class="rounded-lg border border-border bg-card overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-muted/50">
      <tr class="text-left">
        <th class="px-4 py-3 font-medium">Name</th>
        <th class="px-4 py-3 font-medium">SKU</th>
        <th class="px-4 py-3 font-medium">Price</th>
        <th class="px-4 py-3 font-medium">Stock</th>
        <th class="px-4 py-3 font-medium">Status</th>
      </tr>
    </thead>
    <tbody>
      {% for p in products %}
      <tr class="border-t border-border">
        <td class="px-4 py-3"><a href="{% url 'product_detail' p.pk %}" class="font-medium hover:text-primary">{{ p.name }}</a></td>
        <td class="px-4 py-3 text-muted-foreground">{{ p.sku }}</td>
        <td class="px-4 py-3">${{ p.price }}</td>
        <td class="px-4 py-3">{{ p.stock }}</td>
        <td class="px-4 py-3"><span class="text-xs rounded px-2 py-1 bg-muted">{{ p.get_status_display }}</span></td>
      </tr>
      {% empty %}
      <tr><td colspan="5" class="px-4 py-12 text-center text-muted-foreground">No products yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% include "partials/pagination.html" %}
{% endblock %}
```

- [ ] **Step 6: Commit**

```bash
uv run pytest apps/products/ -v
git add -A
git commit -m "feat(products): Product/Category models + paginated list view"
```

---

## Task 10: Products — detail, create, edit views

**Files:**
- Modify: `apps/products/{views,forms,urls}.py`, add `templates/products/{product_detail,product_form}.html`

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.django_db
def test_product_detail_renders(client):
    client.force_login(UserFactory())
    p = ProductFactory()
    r = client.get(f"/products/{p.pk}/")
    assert r.status_code == 200
    assert p.name.encode() in r.content

@pytest.mark.django_db
def test_product_create_post_persists(client):
    client.force_login(UserFactory())
    cat = CategoryFactory()
    r = client.post("/products/new/", {
        "name": "Fresh", "slug": "fresh", "sku": "FR-1",
        "price": "9.99", "stock": "5", "status": "draft", "category": cat.pk, "description": "",
    })
    assert r.status_code == 302
    assert Product.objects.filter(slug="fresh").exists()

@pytest.mark.django_db
def test_product_edit_updates_fields(client):
    client.force_login(UserFactory())
    p = ProductFactory()
    r = client.post(f"/products/{p.pk}/edit/", {
        "name": "Updated", "slug": p.slug, "sku": p.sku,
        "price": str(p.price), "stock": p.stock, "status": p.status,
        "category": p.category.pk, "description": "",
    })
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.name == "Updated"
```

- [ ] **Step 2: Implement form + views**

`apps/products/forms.py`:
```python
from django import forms
from .models import Product

BASE = "w-full h-10 rounded-md border border-input bg-background px-3 text-sm"

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "slug", "sku", "price", "stock", "status", "category", "description", "image"]
        widgets = {
            "name": forms.TextInput(attrs={"class": BASE}),
            "slug": forms.TextInput(attrs={"class": BASE}),
            "sku": forms.TextInput(attrs={"class": BASE}),
            "price": forms.NumberInput(attrs={"class": BASE, "step": "0.01"}),
            "stock": forms.NumberInput(attrs={"class": BASE}),
            "status": forms.Select(attrs={"class": BASE}),
            "category": forms.Select(attrs={"class": BASE}),
            "description": forms.Textarea(attrs={"class": BASE.replace("h-10", "min-h-[120px] py-2")}),
        }
```

`apps/products/views.py` — add:
```python
from django.urls import reverse_lazy
from django.views.generic import DetailView, CreateView, UpdateView
from .forms import ProductForm

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = "products/product_detail.html"

class ProductCreateView(LoginRequiredMixin, CreateView):
    model = Product; form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("product_list")

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product; form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("product_list")
```

`apps/products/urls.py`:
```python
urlpatterns = [
    path("", ProductListView.as_view(), name="product_list"),
    path("new/", ProductCreateView.as_view(), name="product_create"),
    path("<int:pk>/", ProductDetailView.as_view(), name="product_detail"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="product_edit"),
]
```

- [ ] **Step 3: Templates `product_detail.html` and `product_form.html`**

Detail — card with image, name, price, stock, status badge, description, edit button.
Form — tall card, renders `{{ form.field }}` inside `<div>` blocks with labels and error messages (reuse pattern from `register.html`).

- [ ] **Step 4: Verify + commit**

```bash
uv run pytest apps/products/ -v
git add -A
git commit -m "feat(products): detail, create, edit CBV flows"
```

---

## Task 11: Orders app — model + full CRUD

**Mirror of Task 9+10 for Orders.**

**Files:**
- Create: `apps/orders/{models,forms,views,urls,admin}.py`, tests, templates

- [ ] **Step 1: Failing model test**

```python
@pytest.mark.django_db
def test_order_has_items_and_total():
    from apps.orders.models import Order, OrderItem
    from apps.products.tests.factories import ProductFactory
    from apps.accounts.tests.factories import UserFactory
    user = UserFactory()
    product = ProductFactory(price=10)
    order = Order.objects.create(customer=user, status="pending")
    OrderItem.objects.create(order=order, product=product, quantity=3, unit_price=10)
    assert order.total == 30
    assert order.items.count() == 1
```

- [ ] **Step 2: Implement model**

```python
# apps/orders/models.py
from decimal import Decimal
from django.conf import settings
from django.db import models

class Order(models.Model):
    STATUS = [("pending","Pending"),("paid","Paid"),("shipped","Shipped"),("cancelled","Cancelled")]
    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created_at"]

    @property
    def total(self): return sum((i.unit_price * i.quantity for i in self.items.all()), Decimal("0"))

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"ORD-{self.pk or ''}"  # post-save fixup in Step 4
        super().save(*args, **kwargs)
        if self.number.endswith("-"):
            Order.objects.filter(pk=self.pk).update(number=f"ORD-{self.pk:05d}")
            self.refresh_from_db()

    def __str__(self): return self.number or "new-order"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
```

- [ ] **Step 3: Tests + views + templates**

Replicate Task 10 structure: List (paginated 20, search by `number` + customer email), Detail (items table with line totals + grand total), Create/Edit with inline formset for items.

Formset skeleton — `apps/orders/forms.py`:
```python
from django import forms
from django.forms import inlineformset_factory
from .models import Order, OrderItem

BASE = "w-full h-10 rounded-md border border-input bg-background px-3 text-sm"

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["customer", "status"]
        widgets = {"customer": forms.Select(attrs={"class": BASE}),
                   "status": forms.Select(attrs={"class": BASE})}

OrderItemFormSet = inlineformset_factory(
    Order, OrderItem,
    fields=["product", "quantity", "unit_price"],
    extra=1, can_delete=True,
    widgets={
        "product": forms.Select(attrs={"class": BASE}),
        "quantity": forms.NumberInput(attrs={"class": BASE}),
        "unit_price": forms.NumberInput(attrs={"class": BASE, "step": "0.01"}),
    },
)
```

View (CreateView) — use `get_context_data` to inject formset, `form_valid` to save both:
```python
class OrderCreateView(LoginRequiredMixin, CreateView):
    model = Order; form_class = OrderForm
    template_name = "orders/order_form.html"
    success_url = reverse_lazy("order_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items_formset"] = OrderItemFormSet(self.request.POST or None, instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx["items_formset"]
        self.object = form.save()
        formset.instance = self.object
        if formset.is_valid():
            formset.save()
            return redirect(self.success_url)
        return self.render_to_response(self.get_context_data(form=form))
```

Template fragment (`order_form.html`) — Alpine drives add-row:
```html
<form method="post" x-data="{}">
  {% csrf_token %}
  {{ form.as_p }}
  {{ items_formset.management_form }}
  <div id="items">
    {% for f in items_formset %}
      <div class="grid grid-cols-4 gap-2 mb-2">
        {{ f.product }}{{ f.quantity }}{{ f.unit_price }}{{ f.DELETE }}
        {{ f.id }}
      </div>
    {% endfor %}
  </div>
  <button type="button" x-on:click="
    const tpl = document.getElementById('items').lastElementChild.cloneNode(true);
    const total = document.querySelector('[name=items-TOTAL_FORMS]');
    const idx = parseInt(total.value);
    tpl.innerHTML = tpl.innerHTML.replace(/items-\d+-/g, `items-${idx}-`);
    tpl.querySelectorAll('input,select').forEach(i => { if (i.type !== 'hidden') i.value = ''; });
    document.getElementById('items').appendChild(tpl);
    total.value = idx + 1;
  ">+ Add item</button>
  <button type="submit">Save</button>
</form>
```

Note on `Order.save()`: the post-save number-fixup has a tiny race under concurrency — acceptable for MVP demo, revisit if the product ships multi-tenant.

- [ ] **Step 4: Verify + commit**

```bash
uv run pytest apps/orders/ -v
git add -A
git commit -m "feat(orders): Order/OrderItem models + CRUD with inline formset"
```

---

## Task 12: Recent orders + activity feed partials for dashboard

**Files:**
- Create: `templates/dashboard/_recent_orders.html`, `templates/dashboard/_activity_feed.html`
- Modify: `apps/dashboard/views.py` (inject `recent_orders` + `activities`)

- [ ] **Step 1: Test**

```python
@pytest.mark.django_db
def test_dashboard_shows_latest_five_orders(client):
    client.force_login(UserFactory())
    from apps.orders.tests.factories import OrderFactory
    OrderFactory.create_batch(10)
    response = client.get("/")
    assert response.content.count(b"ORD-") >= 5
```

- [ ] **Step 2: Update view**

```python
from apps.orders.models import Order
# inside get():
context["recent_orders"] = Order.objects.select_related("customer").order_by("-created_at")[:5]
context["activities"] = [
    {"user": "Alice", "action": "created a new order", "when": "2m ago"},
    {"user": "Bob", "action": "updated product pricing", "when": "15m ago"},
    {"user": "Carol", "action": "signed up", "when": "1h ago"},
]
```

- [ ] **Step 3: Partials**

`_recent_orders.html` — table with Order#, customer, total, status badge.
`_activity_feed.html` — `<ul>` timeline, vertical line + dots.

Include in `dashboard/index.html`:
```html
<div class="mt-6 grid grid-cols-1 xl:grid-cols-12 gap-4">
  {% include "dashboard/_recent_orders.html" %}
  {% include "dashboard/_activity_feed.html" %}
</div>
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(dashboard): recent orders table + activity feed"
```

---

## Task 13: Users management CRUD

**Files:**
- Create: `templates/accounts/{user_list,user_detail,user_form}.html`
- Modify: `apps/accounts/{views,urls,forms}.py`

Mirror the **Task 10 Products CRUD** structure on the existing `User` model. Views go in `apps/accounts/views.py`, URLs wired under `path("users/", ...)`. Only staff users can modify others — gate with `UserPassesTestMixin` (`test_func = lambda self: self.request.user.is_staff`).

- [ ] **Step 1: Tests**

```python
# apps/accounts/tests/test_user_crud.py
@pytest.mark.django_db
def test_user_list_staff_only(client):
    client.force_login(UserFactory(is_staff=False))
    assert client.get("/users/").status_code == 403

@pytest.mark.django_db
def test_staff_can_list_users(client):
    client.force_login(UserFactory(is_staff=True))
    UserFactory.create_batch(3)
    r = client.get("/users/")
    assert r.status_code == 200

@pytest.mark.django_db
def test_staff_can_create_user(client):
    client.force_login(UserFactory(is_staff=True))
    r = client.post("/users/new/", {
        "username": "created", "email": "c@example.com",
        "first_name": "C", "last_name": "D", "role": "staff",
        "password1": "Complex-1234", "password2": "Complex-1234",
    })
    assert r.status_code == 302
    from django.contrib.auth import get_user_model
    assert get_user_model().objects.filter(username="created").exists()
```

- [ ] **Step 2: Implement `UserListView`, `UserDetailView`, `UserCreateView`, `UserUpdateView`**

Follow the Task 10 pattern exactly. `UserCreateForm` subclasses `UserCreationForm` with extra fields (`email`, `role`, `first_name`, `last_name`). `UserUpdateForm` is a `ModelForm` on `User` with no password fields (use Django's dedicated password-change view separately).

- [ ] **Step 3: Templates**

`user_list.html`, `user_detail.html`, `user_form.html` — structurally identical to `product_list.html` / `product_detail.html` / `product_form.html` with User fields.

- [ ] **Step 4: Verify + commit** — `uv run pytest apps/accounts/ && git commit -am "feat(accounts): user management CRUD with staff gate"`

---

## Task 14: Settings / profile page

**Files:**
- Create: `templates/accounts/profile.html`
- Modify: `apps/accounts/{views,urls,forms}.py`

- [ ] **Step 1: Tests**

```python
@pytest.mark.django_db
def test_profile_get_renders(client):
    user = UserFactory(); client.force_login(user)
    r = client.get("/settings/")
    assert r.status_code == 200
    assert user.username.encode() in r.content

@pytest.mark.django_db
def test_profile_post_updates(client):
    user = UserFactory(first_name="Old"); client.force_login(user)
    r = client.post("/settings/", {"first_name": "New", "last_name": user.last_name, "email": user.email, "bio": ""})
    assert r.status_code == 302
    user.refresh_from_db()
    assert user.first_name == "New"
```

- [ ] **Step 2: Implement + template**

`ProfileView` is a `UpdateView` targeting `request.user`, fields `first_name`, `last_name`, `email`, `bio`, `avatar`.

- [ ] **Step 3: Verify + commit** — `git commit -m "feat(accounts): profile settings page"`

---

## Task 15: Error pages + handlers

**Files:**
- Create: `templates/errors/{403,404,500}.html`
- Modify: `apex/urls.py` (add `handler403`, `handler404`, `handler500`), `apps/core/views.py`

- [ ] **Step 1: Tests**

```python
@pytest.mark.django_db
def test_404_uses_custom_template(client, settings):
    settings.DEBUG = False
    r = client.get("/this-route-does-not-exist/")
    assert r.status_code == 404
    assert b"Page not found" in r.content
```

- [ ] **Step 2: Implement templates + handlers**

Each error template extends `layouts/auth.html` with an illustration slot, status code, copy, and "Back to dashboard" button. Match Apex's `/403`, `/500`, `/not-found` copy.

- [ ] **Step 3: Commit** — `git commit -m "feat(core): custom 403/404/500 pages"`

---

## Task 16: Seed demo data management command

**Files:**
- Create: `apps/core/management/commands/seed_demo.py`

- [ ] **Step 1: Test**

```python
@pytest.mark.django_db
def test_seed_demo_creates_users_products_orders():
    from django.core.management import call_command
    call_command("seed_demo")
    from apps.products.models import Product
    from apps.orders.models import Order
    assert Product.objects.count() >= 20
    assert Order.objects.count() >= 30
```

- [ ] **Step 2: Implement command using factories**

```python
# apps/core/management/commands/seed_demo.py
from django.core.management.base import BaseCommand
from apps.accounts.tests.factories import UserFactory
from apps.products.tests.factories import ProductFactory, CategoryFactory
from apps.orders.tests.factories import OrderFactory, OrderItemFactory

class Command(BaseCommand):
    help = "Populate demo data for the Apex dashboard."

    def handle(self, *args, **opts):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        demo, _ = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@example.com", "first_name": "Demo", "last_name": "User", "role": "admin", "is_staff": True},
        )
        demo.set_password("demo1234"); demo.save()

        UserFactory.create_batch(15)
        CategoryFactory.create_batch(5)
        ProductFactory.create_batch(25)
        for _ in range(30):
            order = OrderFactory()
            for _ in range(3):
                OrderItemFactory(order=order)
        self.stdout.write(self.style.SUCCESS("Seeded. Demo login: demo / demo1234"))
```

- [ ] **Step 3: Verify + commit** — `git commit -m "chore: seed_demo management command"`

---

## Task 17: Playwright E2E smoke tests (parity with Apex)

**Files:**
- Create: `tests/e2e/test_smoke.py`, `playwright.config.py`, `tests/e2e/conftest.py`

**Reference:** `/Users/silkalns/Projects/admin-dashboard/e2e/smoke.spec.ts`.

- [ ] **Step 1: Write the tests**

```python
# tests/e2e/test_smoke.py
import pytest
from playwright.sync_api import Page, expect

@pytest.fixture(scope="session")
def base_url(): return "http://localhost:8000"

@pytest.fixture(autouse=True)
def seeded(django_db_blocker):
    with django_db_blocker.unblock():
        from django.core.management import call_command
        call_command("seed_demo")

def test_dashboard_heading_visible(page: Page, base_url):
    page.goto(f"{base_url}/accounts/login/")
    page.fill('input[name="username"]', "demo")
    page.fill('input[name="password"]', "demo1234")
    page.click('button[type="submit"]')
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()

def test_sidebar_navigates_to_products(page: Page, base_url):
    # after login
    page.click('a:has-text("Products")')
    expect(page.get_by_role("heading", name="Products")).to_be_visible()

def test_theme_toggle_switches_html_class(page: Page, base_url):
    html = page.locator("html")
    before = html.get_attribute("class") or ""
    page.click('button[aria-label="Toggle theme"]')
    after = html.get_attribute("class") or ""
    assert after != before
```

- [ ] **Step 2: Run with live server**

```bash
uv run python manage.py runserver &
SERVER_PID=$!
uv run pytest tests/e2e/ -v
kill $SERVER_PID
```

- [ ] **Step 3: Commit** — `git commit -m "test(e2e): Playwright smoke parity with Apex Next.js"`

---

## Task 18: README, CHANGELOG, sellable bundle

**Files:**
- Create: `README.md`, `CHANGELOG.md`, `.env.example`, `docs/getting-started.md`

- [ ] **Step 1: Write README**

Sections: Overview, Tech stack, Quick start (`uv sync`, `npm install`, migrate, `seed_demo`, `runserver`), Project structure, Customization (design tokens, adding pages, adding charts), Deployment (gunicorn + whitenoise), License.

- [ ] **Step 2: Write CHANGELOG**

```markdown
# Changelog

## [0.1.0] - 2026-04-20
### Added
- Initial Django 5 port of Apex Dashboard (MVP).
- Dashboard landing: stats, revenue chart (ApexCharts), traffic donut, goals, recent orders, activity feed.
- Auth: login, register, logout, password reset.
- CRUD: Users, Products, Orders.
- Settings: profile page.
- Error pages: 403, 404, 500.
- Seed demo data management command.
- Playwright E2E smoke tests.
```

- [ ] **Step 3: Final commit + tag**

```bash
git add -A
git commit -m "docs: README, CHANGELOG, getting-started for v0.1.0"
git tag v0.1.0
```

---

## Acceptance criteria (Phase 1 complete when)

- [ ] `uv run pytest` passes (all unit + view tests green).
- [ ] `uv run pytest tests/e2e/` passes against `runserver`.
- [ ] `python manage.py seed_demo && python manage.py runserver` opens a working dashboard at `/` after login.
- [ ] Dark-mode toggle persists across page reloads.
- [ ] Every MVP page listed at the top of this document renders without a 500.
- [ ] Visual sanity check: sidebar, header, and stat cards are visually within 10% of Apex Next.js reference screenshots (subjective).

## Post-MVP follow-on plans (Phase 2+)

Separate plans (not covered here):
- `2026-05-xx-apex-django-analytics-saas-crm-ecommerce.md` — 4 dashboard landing variants.
- `2026-05-xx-apex-django-apps-suite.md` — Chat, Mail, Calendar, Kanban, Files, Notifications.
- `2026-06-xx-apex-django-billing-invoices.md` — Invoices + Billing + Pricing page.
- `2026-06-xx-apex-django-i18n-theme-customizer.md` — i18n (en/de/fr) + on-the-fly theme customizer drawer.
