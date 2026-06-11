# Phase 9 — i18n

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Wire Django's i18n machinery — `LocaleMiddleware`, `LANGUAGES`, `LOCALE_PATHS`, `set_language` URL — and tag user-visible chrome strings (sidebar, header, dashboard headings, common buttons, login form). Ship Spanish (`es`) as the demo locale. Add a language picker to the nav user menu.

## Context

Final phase of the parity roadmap. Per the [roadmap decision](../plans/2026-04-24-apex-parity-roadmap.md#decisions-proposed-defaults--revise-if-any-feel-wrong), i18n was deferred to Phase 9 to avoid backfilling translations on every prior phase.

Decisions:

- **Locales shipped:** English (default) + Spanish (es) for the demo. Adding more is a one-line settings edit + a new `.po` file.
- **Coverage scope:** Visible *chrome* — sidebar nav labels, header, dashboard landing headings, login form, common buttons. **Not** dynamic content (customer names, message bodies, invoice numbers) — those stay in their original language.
- **Date/number formatting:** Django `USE_L10N` is on by default in Django 5; that auto-formats dates per locale. No extra config.
- **Picker location:** Nav user menu (next to Lock screen).

## Goals

Demonstrate working locale switching: pick Spanish from the user menu, see the sidebar + header + key headings render in Spanish, click again to switch back. Don't aim for exhaustive translation coverage (that's a maintenance project); aim for clearly visible i18n on the surfaces a reviewer would check first.

## Non-goals

- Full coverage of every template string (deferred — partial v1)
- RTL languages (Arabic / Hebrew) layout adjustments
- Locale-specific URL prefixes (`/es/dashboard/`) — uses session-based locale detection
- Translation of dynamic data (customer / invoice / message content)
- Per-user default language preference (uses session/cookie)
- Locale-aware number/currency formatting beyond Django defaults
- Translation memory / external translation service integration

## Features

| Feature | Behaviour |
|---|---|
| **Locale middleware** | Django's `LocaleMiddleware` reads session/cookie/Accept-Language and sets the active locale per request. |
| **LANGUAGES setting** | English + Spanish enabled. |
| **`set_language` view** | Built-in Django view at `/i18n/setlang/` accepts a POST with `language` field and stores it in the session, then redirects. |
| **Language picker** | Nav user-menu submenu with two options (English / Español). POST to `set_language`. |
| **Tagged chrome** | Sidebar nav labels (via `gettext_lazy`), header search placeholder, dashboard headings, login form labels, common buttons (Save / Cancel / Delete / Send). |
| **Spanish translations** | Hand-written `.po` for each tagged string. Compiled to `.mo` for runtime use. |

## Architecture

### Settings

```python
# apex/settings/base.py
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

MIDDLEWARE = [
    # ... existing ...
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",   # ← NEW (after sessions)
    "django.middleware.common.CommonMiddleware",
    # ... existing ...
]
```

### URLs

```python
# apex/urls.py
from django.conf.urls.i18n import i18n_patterns  # not used; we stay session-based
urlpatterns = [
    # ...
    path("i18n/", include("django.conf.urls.i18n")),  # provides /i18n/setlang/
    # ...
]
```

### Sidebar nav with `gettext_lazy`

```python
# apps/core/navigation.py
from django.utils.translation import gettext_lazy as _

NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem(_("Dashboard"), "dashboard", "layout-dashboard", ...),
    NavItem(_("Orders"), "orders:list", ...),
    # ...
)
```

`NavItem.label` is a lazy translation object; rendering in templates resolves at request time per active locale.

### Templates

Top of every modified template:

```django
{% load i18n %}
```

String tagging:

```django
<h1>{% trans "Welcome back" %}</h1>
<p>{% blocktrans %}Hello, {{ name }}!{% endblocktrans %}</p>
```

### Language picker

In `templates/partials/nav_user_menu.html`:

```django
<form method="post" action="{% url 'set_language' %}" class="border-t border-border p-2">
  {% csrf_token %}
  <input type="hidden" name="next" value="{{ request.path }}">
  <label class="block px-1 py-1 text-xs uppercase tracking-wider text-muted-foreground">{% trans "Language" %}</label>
  <select name="language" onchange="this.form.submit()" class="w-full h-8 rounded-md border border-input bg-background px-2 text-sm">
    {% get_current_language as LANG %}
    {% get_available_languages as LANGUAGES %}
    {% for code, name in LANGUAGES %}
      <option value="{{ code }}" {% if code == LANG %}selected{% endif %}>{{ name }}</option>
    {% endfor %}
  </select>
</form>
```

## Coverage scope (concrete)

**v1 tagged surfaces:**

- `apps/core/navigation.py` — all NAV_ITEMS labels
- `templates/partials/header.html` — search placeholder, action buttons aria-labels
- `templates/partials/sidebar.html` — group headings (Overview / Commerce / Apps / Marketing / Showcase / Account)
- `templates/dashboard/index.html` — page heading
- `templates/registration/login.html` — labels, button text
- `templates/marketing/base.html` — Sign in / Dashboard CTAs

**Out of v1 scope (English-only):**

- App-specific list/detail/form labels (Mail/Chat/Invoice/etc.)
- Flash messages
- Form validation errors
- Admin site
- Email templates

These can be tagged incrementally without breaking the i18n machinery.

## Testing

### Unit (~3 new tests)

- Setting language via session affects translated strings (Spanish "Tablero" returned for "Dashboard")
- POST to `/i18n/setlang/` updates the session locale
- `LANGUAGES` setting includes both `en` and `es`

### E2E (~1 new test)

- Switch language to Español → sidebar shows translated labels → switch back

## Rollout — 4 commits (incl. docs)

1. docs
2. Settings + LocaleMiddleware + URLs + sidebar nav `gettext_lazy` + tag a handful of chrome templates
3. Spanish .po file with translations + compile (.mo)
4. Language picker in nav user menu + E2E test

## Open questions

1. **Locale persistence:** session-only (resets on logout) or cookie-based (persists across sessions)? Django's `set_language` uses both — cookie-first, session as fallback. *Proposed:* default behavior (cookie) is fine.
2. **Translation source:** hand-written for v1. AI / external service if scope grows.
