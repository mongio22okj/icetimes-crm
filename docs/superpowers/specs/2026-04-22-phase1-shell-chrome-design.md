# Phase 1 — Shell & Chrome Upgrade

**Date:** 2026-04-22
**Status:** Approved (brainstorming)
**Scope:** First of a 7-phase port of the Apex Next.js/Laravel dashboard to Django-native. This phase upgrades the app shell so every page added in later phases inherits the richer chrome.

## Context

The Django port (v0.1.0) has ~15 pages; the reference Apex (the `dashboardpack-apex-laravel` sibling) has ~72. The port's shell is functional but missing several signature pieces of Apex UX. Phase 1 closes the shell-level gap so subsequent phases can focus purely on page content.

## Goals

Match the reference shell's feature parity while staying faithful to the project's stack (Django 5 + Tailwind v4 + Alpine.js + HTMX — no JS build step, no SPA framework).

## Non-goals

- DB-backed search in the palette (nav + static actions only, like the reference)
- Re-theming or colour changes (already shipped in v0.1.0 polish pass)
- Touching any page content — only the shell chrome
- Deferred pages (customers, invoices, roles, extra dashboards, apps, docs, landing) — those belong to Phases 2–7

## Features

Six shell upgrades, all in-scope:

| # | Feature | Behaviour |
|---|---------|-----------|
| A | Command palette | ⌘K / Ctrl+K opens modal. Sections: **Pages** (from `NAV_ITEMS`, staff-filtered), **Actions** (New order, Toggle theme), **Quick links** (Documentation link — placeholder URL for Phase 7). Substring match on `label + keywords`. |
| B | Mobile sidebar | Hidden below `lg` breakpoint; hamburger button in header opens a slide-in drawer with overlay backdrop. Closes on link click, Esc, or backdrop tap. |
| C | Nav-user dropdown | Header avatar becomes a dropdown showing the current user's name, email, role. Menu items: Profile, Settings, Sign out. Sidebar footer user tile stays (consolidation deferred). |
| D | Breadcrumbs bar | Secondary row below main header, visible only when ≥2 crumbs. Per-view definitions via `BreadcrumbsMixin`. |
| E | Header search rewire | The currently cosmetic search input becomes the palette trigger (whole-input click opens palette). Shows `⌘K` hint chip on the right. |
| F | Richer nav metadata | Each nav item gains `keywords`, optional `badge`, `requires_staff`. Single source of truth in `apps/core/navigation.py`, consumed by both sidebar and palette. |

## Architecture

Single root Alpine component `apexShell()` on `<body>` in `base.html`. Holds shared state that must coordinate:

- `palette: { open, query, selectedIndex, items }`
- `drawer: { open }`
- `theme: 'light' | 'dark'` (moved from current inline x-data)

The nav-user dropdown stays as a local `x-data` because it doesn't need to coordinate with the others. Breadcrumbs are pure template output (no JS state).

```
base.html (x-data="apexShell()")
├── sidebar.html                 — mobile: x-show="drawer.open" + transitions; lg: always visible
├── header.html
│   ├── hamburger (mobile)       — @click="drawer.open = true"
│   ├── search trigger           — @click="palette.open = true"
│   ├── theme toggle             — uses apexShell theme state
│   └── nav_user_menu.html       — own x-data
├── breadcrumbs.html             — conditional render
├── {% block content %}
└── command_palette.html         — mounted once, reads nav items from <script type="application/json" id="nav-items">
```

## Data model

### Navigation — `apps/core/navigation.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    keywords: tuple[str, ...] = ()
    badge: str | None = None
    requires_staff: bool = False

NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("Dashboard", "dashboard", "layout-dashboard", ("home", "overview")),
    NavItem("Orders", "orders:list", "shopping-cart", ("sales", "purchases")),
    NavItem("Products", "products:list", "package", ("inventory", "catalog")),
    NavItem("Users", "users:list", "users", ("team", "staff"), requires_staff=True),
    NavItem("Settings", "settings:profile", "settings",
            ("account", "profile", "preferences")),
)

def get_visible_items(user) -> list[NavItem]:
    """Filter NAV_ITEMS by staff requirement."""
    return [i for i in NAV_ITEMS if not i.requires_staff or user.is_staff]
```

Context processor (`apps/core/context_processors.py`) exposes:
- `nav_groups` — sidebar-shaped list of `(group_label, [NavItem, …])`
- `nav_items_json` — list of `{label, url, icon, keywords, badge}` dicts with resolved URLs, for `{{ nav_items_json|json_script:"nav-items" }}`

### Breadcrumbs — `apps/core/breadcrumbs.py`

```python
from django.urls import reverse

class BreadcrumbsMixin:
    breadcrumb_title: str | None = None
    # Either a URL name or (title, url_name) tuple. Use tuple when the parent title
    # differs from what the URL resolves to (rare).
    breadcrumb_parent: str | tuple[str, str] | None = None

    def get_breadcrumb_title(self) -> str:
        return self.breadcrumb_title or ""

    def get_breadcrumbs(self) -> list[tuple[str, str | None]]:
        crumbs: list[tuple[str, str | None]] = [("Dashboard", reverse("dashboard"))]
        # Walk parent chain
        parent = self.breadcrumb_parent
        while parent:
            if isinstance(parent, tuple):
                title, url_name = parent
            else:
                title, url_name = self._resolve_parent_title(parent), parent
            crumbs.append((title, reverse(url_name)))
            parent = None  # one level deep is enough for MVP; extend if needed
        crumbs.append((self.get_breadcrumb_title(), None))  # current
        return crumbs

    def _resolve_parent_title(self, url_name: str) -> str:
        # Lookup via NAV_ITEMS for consistent labelling
        from apps.core.navigation import NAV_ITEMS
        for item in NAV_ITEMS:
            if item.url_name == url_name:
                return item.label
        return url_name.replace(":", " / ").title()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = self.get_breadcrumbs()
        return ctx
```

Dynamic titles (e.g., "ORD-00029" on order detail) override `get_breadcrumb_title()`.

## Component inventory

**New**

| File | Purpose |
|------|---------|
| `apps/core/navigation.py` | `NavItem`, `NAV_ITEMS`, `get_visible_items` |
| `apps/core/breadcrumbs.py` | `BreadcrumbsMixin` |
| `templates/partials/command_palette.html` | Palette modal |
| `templates/partials/nav_user_menu.html` | Header avatar dropdown |
| `templates/partials/breadcrumbs.html` | Breadcrumb bar (inclusion tag target) |
| `static/js/shell.js` | `apexShell()` Alpine factory |

**Modified**

| File | Change |
|------|--------|
| `templates/base.html` | Root `x-data="apexShell()"`, load `shell.js`, mount palette, include breadcrumbs, emit nav-items JSON |
| `templates/partials/sidebar.html` | Mobile transitions, close-X on mobile, consume new `nav_groups` |
| `templates/partials/header.html` | Hamburger, search-as-trigger with ⌘K chip, static avatar → dropdown |
| `apps/core/context_processors.py` | Pull from `navigation.py`, expose `nav_items_json` |
| `apps/core/templatetags/apex.py` | Add `breadcrumbs` inclusion tag |
| Every CBV in `apps/dashboard/views.py`, `apps/orders/views.py`, `apps/products/views.py`, `apps/accounts/views.py` | Mix in `BreadcrumbsMixin` and declare `breadcrumb_title` / `breadcrumb_parent` |

## Keyboard + accessibility

| Shortcut | Behaviour |
|----------|-----------|
| ⌘K / Ctrl+K | Open palette, focus input |
| ⌘/ / Ctrl+/ | Same as above (alt convention) |
| Esc | Close topmost overlay (palette > drawer) |
| ↑ ↓ | Move palette selection |
| Enter | Activate selected palette item |

Palette and drawer both use `role="dialog"` + `aria-modal="true"`, focus trap on Tab, return focus to trigger on close. Body scroll-lock via `document.body.style.overflow = 'hidden'` while either is open. Nav-user dropdown uses `role="menu"`, arrow-key nav, click-outside close.

## Error handling

- **Bad `url_name` in `NavItem`**: `get_nav_items_json()` raises at app startup (context-processor load), surfacing in dev immediately. No silent skip.
- **Missing `breadcrumb_title` on a view using the mixin**: returns empty string — breadcrumb still renders with empty final crumb (visually obvious). Not worth hard-failing.
- **Palette keyboard handler**: guards against input fields (don't trigger ⌘K while typing in `<input>`, `<textarea>`, `contenteditable`).
- **Drawer + palette open simultaneously**: palette wins (higher z-index, Esc closes it first, then drawer on next Esc).

## Testing

**Unit (pytest, +6 tests)**

1. `BreadcrumbsMixin` chain resolution — order-edit view yields `[Dashboard, Orders, ORD-…]`
2. `navigation.get_visible_items` — non-staff user cannot see Users item
3. `{% breadcrumbs %}` tag renders nothing when `len(breadcrumbs) < 2`
4. `nav_items_json` excludes staff-only items for non-staff users
5. Context processor exposes both `nav_groups` and `nav_items_json` consistently
6. `NavItem.url_name` that doesn't resolve raises `NoReverseMatch` at context-processor load

**E2E (Playwright, +5 tests)**

1. ⌘K opens palette; typing `"ord"` highlights Orders; Enter navigates to `/orders/`
2. Hamburger opens drawer on mobile viewport; clicking a drawer link navigates and drawer closes
3. Header avatar click opens dropdown; "Sign out" button posts logout and redirects to login
4. Order detail breadcrumb trail reads `Dashboard / Orders / ORD-<n>`
5. Demo user (non-staff in seed) doesn't see Users in palette search results

## Rollout

Two commits for bisect-friendliness:

1. **Shell** — navigation module, palette, drawer, dropdown, header rewire, `shell.js`, unit tests, 3 E2E tests
2. **Breadcrumbs** — mixin + tag + view sweep + breadcrumbs tests (2 E2E)

## Open questions

None — user approved scope, approach, data model, files touched, and tests. Spec-review subagent loop skipped at user's request to keep momentum.
