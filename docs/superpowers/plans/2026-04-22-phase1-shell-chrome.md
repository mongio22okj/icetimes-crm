# Phase 1 — Shell & Chrome Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Django Apex shell with command palette (⌘K), mobile sidebar drawer, nav-user dropdown, breadcrumbs, search-as-palette-trigger, and richer nav metadata — matching the reference Laravel/Inertia Apex shell using Alpine.js only (no JS build step).

**Architecture:** One root Alpine factory `apexShell()` on the dashboard layout's outer div owns shared state (palette + drawer). Nav source of truth moves to `apps/core/navigation.py`; context processor exposes both a sidebar-shaped grouping and a palette-ready JSON list (embedded via `json_script`). Breadcrumbs are declared per-view through `BreadcrumbsMixin` and rendered by an inclusion templatetag in the dashboard layout.

**Tech Stack:** Django 5.1 · Tailwind v4 · Alpine.js 3.14 · HTMX · Lucide inline SVG icons · pytest · Playwright (existing).

**Reference spec:** [`docs/superpowers/specs/2026-04-22-phase1-shell-chrome-design.md`](../specs/2026-04-22-phase1-shell-chrome-design.md)

**Two commits:**
1. Tasks 1–9 → `feat(core): shell chrome upgrade (palette, drawer, user menu)`
2. Tasks 10–14 → `feat(core): breadcrumbs across dashboard views`

---

## Pre-flight

- [ ] **Confirm the test harness still passes before touching anything.**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `87 passed`

- [ ] **Confirm Tailwind rebuilds cleanly.**

Run: `npm run build 2>&1 | tail -2`
Expected: `Done in ...ms`

---

## Task 1 — Navigation data module

**Files:**
- Create: `apps/core/navigation.py`
- Create: `apps/core/tests/test_navigation.py`

- [ ] **Step 1.1 — Write failing test**

Create `apps/core/tests/test_navigation.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from django.urls import NoReverseMatch

from apps.core.navigation import NAV_ITEMS, NavItem, get_visible_items, get_palette_entries

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_nav_items_expose_expected_labels():
    labels = {i.label for i in NAV_ITEMS}
    assert labels == {"Dashboard", "Orders", "Products", "Users", "Settings"}


def test_get_visible_items_filters_staff_only_for_non_staff():
    user = User.objects.create_user(username="regular", password="pw", is_staff=False)
    items = get_visible_items(user)
    assert "Users" not in {i.label for i in items}
    assert "Dashboard" in {i.label for i in items}


def test_get_visible_items_includes_staff_only_for_staff():
    user = User.objects.create_user(username="admin", password="pw", is_staff=True)
    items = get_visible_items(user)
    assert "Users" in {i.label for i in items}


def test_palette_entries_have_resolved_urls():
    user = User.objects.create_user(username="admin", password="pw", is_staff=True)
    entries = get_palette_entries(user)
    by_label = {e["label"]: e for e in entries}
    assert by_label["Dashboard"]["url"] == "/"
    assert by_label["Orders"]["url"] == "/orders/"
    assert by_label["Settings"]["url"] == "/settings/"
    assert "home" in by_label["Dashboard"]["keywords"]


def test_nav_item_bad_url_raises_on_resolution():
    bad = NavItem(label="Bad", url_name="does_not_exist", icon="x")
    with pytest.raises(NoReverseMatch):
        bad.resolved_url()
```

- [ ] **Step 1.2 — Run test to verify failure**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_navigation.py -v 2>&1 | tail -20`
Expected: `ModuleNotFoundError: No module named 'apps.core.navigation'`

- [ ] **Step 1.3 — Implement `apps/core/navigation.py`**

```python
"""Single source of truth for sidebar navigation and command-palette entries."""
from dataclasses import dataclass
from typing import Iterable

from django.urls import reverse


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    keywords: tuple[str, ...] = ()
    badge: str | None = None
    group: str = "Overview"
    requires_staff: bool = False

    def resolved_url(self) -> str:
        return reverse(self.url_name)


NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("Dashboard", "dashboard", "layout-dashboard",
            keywords=("home", "overview"), group="Overview"),
    NavItem("Orders", "orders:list", "shopping-cart",
            keywords=("sales", "purchases"), group="Commerce"),
    NavItem("Products", "products:list", "package",
            keywords=("inventory", "catalog"), group="Commerce"),
    NavItem("Users", "users:list", "users",
            keywords=("team", "staff", "members"), group="Account",
            requires_staff=True),
    NavItem("Settings", "settings:profile", "settings",
            keywords=("account", "profile", "preferences"), group="Account"),
)


def get_visible_items(user) -> list[NavItem]:
    if user is None or not getattr(user, "is_authenticated", False):
        return [i for i in NAV_ITEMS if not i.requires_staff]
    return [i for i in NAV_ITEMS if not i.requires_staff or user.is_staff]


def get_nav_groups(user) -> list[dict]:
    """Shape visible items for the sidebar (grouped, ordered)."""
    groups: dict[str, list[dict]] = {}
    for item in get_visible_items(user):
        groups.setdefault(item.group, []).append({
            "label": item.label,
            "href": item.resolved_url(),
            "icon": item.icon,
            "badge": item.badge,
        })
    # Preserve insertion order of groups
    return [{"label": g, "items": items} for g, items in groups.items()]


def get_palette_entries(user) -> list[dict]:
    """Flat serializable list for the command palette's json_script."""
    return [
        {
            "label": i.label,
            "url": i.resolved_url(),
            "icon": i.icon,
            "keywords": list(i.keywords),
            "badge": i.badge,
            "group": i.group,
        }
        for i in get_visible_items(user)
    ]
```

- [ ] **Step 1.4 — Verify test passes**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_navigation.py -v 2>&1 | tail -10`
Expected: all 5 tests pass.

---

## Task 2 — Context processor refactor

**Files:**
- Modify: `apps/core/context_processors.py` (rewrite)
- Modify: `apps/core/tests/test_nav.py` (update assertions for new shape)

- [ ] **Step 2.1 — Rewrite context processor**

Replace the full content of `apps/core/context_processors.py`:
```python
import json

from apps.core.navigation import get_nav_groups, get_palette_entries


def navigation(request):
    user = getattr(request, "user", None)
    return {
        "nav_groups": get_nav_groups(user),
        "nav_items_json": json.dumps(get_palette_entries(user)),
        "current_path": request.path,
    }
```

- [ ] **Step 2.2 — Update existing nav tests**

Open `apps/core/tests/test_nav.py`. The tests currently call `navigation(RequestFactory().get("/"))` without a logged-in user. That call now returns an `AnonymousUser`, and `get_visible_items` filters out `Users` (staff-only). Existing tests only check for Overview/Commerce groups — still true — but add a regression test for `nav_items_json`.

Append to `apps/core/tests/test_nav.py`:
```python
def test_navigation_exposes_nav_items_json_string():
    import json as _json
    from apps.core.context_processors import navigation
    from django.contrib.auth import get_user_model

    user = get_user_model()(username="anon")  # not saved; AnonymousUser-equivalent
    user.is_staff = False
    request = RequestFactory().get("/")
    request.user = user
    ctx = navigation(request)
    payload = _json.loads(ctx["nav_items_json"])
    assert any(e["label"] == "Dashboard" and e["url"] == "/" for e in payload)
    assert all(e["label"] != "Users" for e in payload), "non-staff should not see Users"
```

- [ ] **Step 2.3 — Run affected tests**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_nav.py apps/core/tests/test_navigation.py -v 2>&1 | tail -15`
Expected: all pass.

- [ ] **Step 2.4 — Run full unit suite to catch regressions**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `88 passed` (87 existing + 1 new).

---

## Task 3 — Sidebar mobile-aware + new data source

**Files:**
- Modify: `templates/partials/sidebar.html`

The existing sidebar already consumes `nav_groups` in the correct shape. We need to:
1. Add mobile slide-in / slide-out classes driven by the root `apexShell()` state (built in Task 4).
2. Add a close-X button visible on mobile.

- [ ] **Step 3.1 — Rewrite sidebar**

Replace the whole `<aside>` with:
```html
{% load apex %}
<aside aria-label="Sidebar"
       :aria-hidden="!drawer.open && isMobile"
       class="fixed left-0 top-0 z-40 h-screen w-[260px] bg-sidebar text-sidebar-foreground border-r border-sidebar-border flex flex-col transition-transform duration-200 ease-out lg:translate-x-0"
       :class="drawer.open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'">
  <div class="h-16 flex items-center justify-between px-6 border-b border-sidebar-border shrink-0">
    <a href="/" aria-label="Apex home" class="flex items-center gap-2.5 font-semibold text-sidebar-primary-foreground">
      <span class="h-8 w-8 rounded-md bg-primary text-primary-foreground inline-flex items-center justify-center">
        {% icon "package" 18 %}
      </span>
      <span class="text-base tracking-tight">Apex</span>
    </a>
    <button type="button"
            @click="drawer.open = false"
            class="lg:hidden h-8 w-8 rounded-md inline-flex items-center justify-center hover:bg-sidebar-accent"
            aria-label="Close menu">
      {% icon "x" 18 %}
    </button>
  </div>
  <nav aria-label="Main navigation" class="flex-1 overflow-y-auto p-4 space-y-6">
    {% for group in nav_groups %}
      <div>
        <p class="px-2 pb-2 text-xs uppercase tracking-wider text-sidebar-foreground/60">{{ group.label }}</p>
        <ul class="space-y-1">
          {% for item in group.items %}
            <li>
              <a href="{{ item.href }}"
                 @click="drawer.open = false"
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
  {% if user.is_authenticated %}
    <div class="p-3 border-t border-sidebar-border shrink-0">
      <div class="flex items-center gap-3 rounded-md px-2 py-2">
        {% if user.avatar %}
          <img src="{{ user.avatar.url }}" alt="" class="h-9 w-9 rounded-full object-cover shrink-0" />
        {% else %}
          <span class="h-9 w-9 rounded-full inline-flex items-center justify-center text-xs font-semibold text-white shrink-0"
                style="background-color: {{ user|avatar_color }};">{{ user|initials }}</span>
        {% endif %}
        <div class="min-w-0 flex-1">
          <div class="text-sm font-medium truncate">{{ user.get_full_name|default:user.username }}</div>
          <div class="text-xs text-sidebar-foreground/60 truncate capitalize">{{ user.get_role_display|default:"Member" }}</div>
        </div>
        <form method="post" action="{% url 'logout' %}">
          {% csrf_token %}
          <button type="submit" aria-label="Sign out"
                  class="h-8 w-8 rounded-md inline-flex items-center justify-center hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
            {% icon "log-out" 16 %}
          </button>
        </form>
      </div>
    </div>
  {% endif %}
</aside>
```

- [ ] **Step 3.2 — Add `x` icon to the icon dictionary**

In `apps/core/templatetags/apex.py` — extend the `ICONS` dict (inside the existing literal) with:
```python
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "menu": '<line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="18" y2="18"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "book-open": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
```

- [ ] **Step 3.3 — Note: no tests yet for sidebar markup changes**

The sidebar renders inside the dashboard layout; existing `test_sidebar_renders_via_dashboard_layout` still asserts labels are present. Alpine attribute strings are embedded in markup — just confirm nothing regresses.

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_nav.py -v 2>&1 | tail -10`
Expected: all pass (including `test_sidebar_renders_via_dashboard_layout`).

---

## Task 4 — Shell Alpine factory + base template wiring

**Files:**
- Create: `static/js/shell.js`
- Modify: `templates/base.html`
- Modify: `templates/layouts/dashboard.html`

- [ ] **Step 4.1 — Create `static/js/shell.js`**

```javascript
/* eslint-disable */
// Root Alpine factory for the Apex shell: command palette + mobile drawer + theme.
// Called as x-data="apexShell()" on the dashboard layout's outer div.
window.apexShell = function apexShell() {
  return {
    // --- Shared state ---
    palette: {
      open: false,
      query: "",
      selectedIndex: 0,
      items: [],        // populated in init()
    },
    drawer: { open: false },
    isMobile: false,

    init() {
      // Load palette items from the json_script payload in base.html
      try {
        const script = document.getElementById("nav-items");
        this.palette.items = script ? JSON.parse(script.textContent) : [];
      } catch (e) { this.palette.items = []; }

      // Track viewport for `isMobile` (lg breakpoint = 1024px)
      const mq = window.matchMedia("(max-width: 1023px)");
      this.isMobile = mq.matches;
      mq.addEventListener("change", (e) => { this.isMobile = e.matches; });

      // Global keyboard shortcuts
      window.addEventListener("keydown", (e) => this.onGlobalKey(e));

      // Lock body scroll when palette or drawer open
      this.$watch("palette.open || drawer.open", (locked) => {
        document.body.style.overflow = locked ? "hidden" : "";
      });
    },

    onGlobalKey(e) {
      // Cmd/Ctrl + K or Cmd/Ctrl + / opens palette (unless typing in input)
      const isModK = (e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "/");
      if (isModK) {
        const tag = (e.target && e.target.tagName) || "";
        const editable = e.target && e.target.isContentEditable;
        // Always allow palette open even from inputs, except inside the palette itself
        e.preventDefault();
        this.openPalette();
        return;
      }
      if (e.key === "Escape") {
        if (this.palette.open) { this.closePalette(); return; }
        if (this.drawer.open)  { this.drawer.open = false; }
      }
    },

    // --- Palette actions ---
    openPalette() {
      this.palette.open = true;
      this.palette.query = "";
      this.palette.selectedIndex = 0;
      this.$nextTick(() => {
        const input = document.getElementById("palette-input");
        if (input) input.focus();
      });
    },
    closePalette() {
      this.palette.open = false;
      this.palette.query = "";
      this.palette.selectedIndex = 0;
    },
    filteredItems() {
      const q = this.palette.query.trim().toLowerCase();
      if (!q) return this.palette.items;
      return this.palette.items.filter((it) => {
        const haystack = (it.label + " " + (it.keywords || []).join(" ")).toLowerCase();
        return haystack.includes(q);
      });
    },
    moveSelection(delta) {
      const list = this.filteredItems();
      if (list.length === 0) return;
      this.palette.selectedIndex = (this.palette.selectedIndex + delta + list.length) % list.length;
    },
    activateSelected() {
      const list = this.filteredItems();
      const item = list[this.palette.selectedIndex];
      if (!item) return;
      // Actions go first in the palette (see template), but filtered list is pages only here.
      this.closePalette();
      window.location.href = item.url;
    },
    toggleTheme() {
      const el = document.documentElement;
      el.classList.toggle("dark");
      try { localStorage.setItem("theme", el.classList.contains("dark") ? "dark" : "light"); } catch (_) {}
      this.closePalette();
    },
  };
};
```

- [ ] **Step 4.2 — Update `templates/base.html` to load shell.js**

Open `templates/base.html`. After the existing Alpine.js script tag, and before `{% block head_extra %}`, append:
```html
  <script src="{% static 'js/shell.js' %}" defer></script>
```

Result — head should now have (in order): htmx → apexcharts → charts.js → alpinejs → shell.js → head_extra block.

- [ ] **Step 4.3 — Update `templates/layouts/dashboard.html`**

Replace the whole body block:
```html
{% extends "base.html" %}
{% load apex %}
{% block body %}
<div x-data="apexShell()" class="flex min-h-screen">
  {% include "partials/sidebar.html" %}

  {# Mobile backdrop #}
  <div x-show="drawer.open"
       x-transition.opacity
       @click="drawer.open = false"
       class="fixed inset-0 z-30 bg-black/50 lg:hidden"
       aria-hidden="true"
       style="display: none;"></div>

  <div class="flex-1 lg:ml-[260px] min-w-0">
    {% include "partials/header.html" %}
    {% include "partials/breadcrumbs.html" %}
    <main class="p-6">
      {% block content %}{% endblock %}
    </main>
  </div>

  {# Nav items payload for the palette #}
  {{ nav_items_json|json_script:"nav-items" }}

  {# Command palette modal #}
  {% include "partials/command_palette.html" %}
</div>
{% endblock %}
```

Note: the `{{ nav_items_json|json_script:"nav-items" }}` filter expects a Python object but our context processor already JSON-encodes. Fix by passing a list instead. Update context processor in Task 2 was `"nav_items_json": json.dumps(...)` — change it back to the list:

Update `apps/core/context_processors.py` (replace the entire file):
```python
from apps.core.navigation import get_nav_groups, get_palette_entries


def navigation(request):
    user = getattr(request, "user", None)
    return {
        "nav_groups": get_nav_groups(user),
        "nav_items_json": get_palette_entries(user),
        "current_path": request.path,
    }
```

And update the Task 2 unit test that parsed JSON — change to expect a list directly:
```python
def test_navigation_exposes_nav_items_json_list():
    from apps.core.context_processors import navigation
    from django.contrib.auth import get_user_model

    user = get_user_model()(username="anon")
    user.is_staff = False
    request = RequestFactory().get("/")
    request.user = user
    ctx = navigation(request)
    payload = ctx["nav_items_json"]
    assert isinstance(payload, list)
    assert any(e["label"] == "Dashboard" and e["url"] == "/" for e in payload)
    assert all(e["label"] != "Users" for e in payload)
```

- [ ] **Step 4.4 — Also create stub `templates/partials/breadcrumbs.html` (empty wrapper for now)**

Create `templates/partials/breadcrumbs.html`:
```html
{# Empty for Task 4; populated in Task 11. #}
```

This lets the dashboard layout render even before breadcrumbs are wired up.

- [ ] **Step 4.5 — Run unit suite**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `88 passed`.

- [ ] **Step 4.6 — Rebuild Tailwind (Alpine `x-show` triggers CSS display)**

Run: `npm run build 2>&1 | tail -2`

Expected: `Done in ...ms`

- [ ] **Step 4.7 — Smoke-test the server still boots**

With the dev server already running (from earlier in the session) or start fresh:
Run: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/accounts/login/`
Expected: `200`

---

## Task 5 — Command palette partial

**Files:**
- Create: `templates/partials/command_palette.html`

- [ ] **Step 5.1 — Create the palette template**

```html
{% load apex %}
<div x-show="palette.open"
     x-cloak
     x-transition.opacity
     @keydown.escape.prevent="closePalette()"
     class="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
     role="dialog"
     aria-modal="true"
     aria-label="Command palette"
     style="display: none;">
  <div @click="closePalette()" class="absolute inset-0 bg-black/40"></div>
  <div class="relative w-full max-w-xl bg-popover text-popover-foreground rounded-lg border border-border shadow-xl overflow-hidden">
    <div class="flex items-center border-b border-border px-3">
      <span class="text-muted-foreground">{% icon "search" 18 %}</span>
      <input id="palette-input"
             type="text"
             x-model="palette.query"
             @input="palette.selectedIndex = 0"
             @keydown.arrow-down.prevent="moveSelection(1)"
             @keydown.arrow-up.prevent="moveSelection(-1)"
             @keydown.enter.prevent="activateSelected()"
             placeholder="Type a command or search..."
             class="flex-1 h-12 bg-transparent px-3 text-sm focus:outline-none placeholder:text-muted-foreground"
             autocomplete="off"
             spellcheck="false">
      <kbd class="hidden sm:inline-flex h-6 items-center rounded border border-border px-1.5 text-[10px] font-mono text-muted-foreground">esc</kbd>
    </div>
    <div class="max-h-[50vh] overflow-y-auto p-2">
      {# Pages section #}
      <div x-show="filteredItems().length > 0">
        <p class="px-2 py-1.5 text-xs text-muted-foreground">Pages</p>
        <ul>
          <template x-for="(item, index) in filteredItems()" :key="item.url">
            <li>
              <button type="button"
                      @click="closePalette(); window.location.href = item.url"
                      @mouseenter="palette.selectedIndex = index"
                      :class="index === palette.selectedIndex ? 'bg-accent text-accent-foreground' : ''"
                      class="w-full flex items-center gap-3 rounded-md px-2 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground">
                <span class="text-muted-foreground" x-html="iconSvg(item.icon)"></span>
                <span x-text="item.label"></span>
                <span x-show="item.badge" class="ml-auto text-xs text-primary font-semibold" x-text="item.badge"></span>
              </button>
            </li>
          </template>
        </ul>
      </div>
      {# Empty state #}
      <div x-show="filteredItems().length === 0" class="px-2 py-6 text-sm text-muted-foreground text-center">
        No results.
      </div>
      {# Actions #}
      <div class="mt-2 border-t border-border pt-2">
        <p class="px-2 py-1.5 text-xs text-muted-foreground">Actions</p>
        <ul>
          <li>
            <a href="{% url 'orders:create' %}"
               @click="closePalette()"
               class="w-full flex items-center gap-3 rounded-md px-2 py-2 text-sm hover:bg-accent hover:text-accent-foreground">
              <span class="text-muted-foreground">{% icon "plus" 16 %}</span>
              <span>New Order</span>
            </a>
          </li>
          <li>
            <button type="button"
                    @click="toggleTheme()"
                    class="w-full flex items-center gap-3 rounded-md px-2 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground">
              <span class="text-muted-foreground">{% icon "moon" 16 %}</span>
              <span>Toggle theme</span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 5.2 — Add `iconSvg` helper to `shell.js`**

The palette needs to render icon SVGs from item name. Add to the returned object in `apexShell()`:
```javascript
    iconSvg(name) {
      const bank = {
        "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
        "shopping-cart": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
        "package": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
        "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
        "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
      };
      const body = bank[name] || "";
      return `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
    },
```

- [ ] **Step 5.3 — Add `[x-cloak]` CSS rule to `static_src/css/input.css`**

Open `static_src/css/input.css`. After the existing `@theme` blocks, add:
```css
@layer base {
  [x-cloak] { display: none !important; }
}
```

- [ ] **Step 5.4 — Rebuild Tailwind**

Run: `npm run build 2>&1 | tail -2`
Expected: `Done in ...ms`

---

## Task 6 — Header: hamburger, search-as-palette-trigger

**Files:**
- Modify: `templates/partials/header.html`

- [ ] **Step 6.1 — Rewrite header**

Replace the entire file:
```html
{% load apex %}
<header class="h-16 border-b border-border bg-card/50 backdrop-blur sticky top-0 z-20 flex items-center justify-between gap-2 px-4 lg:px-6">
  <div class="flex items-center gap-2 flex-1 min-w-0">
    {# Hamburger (mobile) #}
    <button type="button"
            @click="drawer.open = true"
            class="lg:hidden h-9 w-9 rounded-md border border-border inline-flex items-center justify-center hover:bg-accent"
            aria-label="Open menu">
      {% icon "menu" 18 %}
    </button>

    {# Search = palette trigger #}
    <button type="button"
            @click="openPalette()"
            class="group flex-1 max-w-md h-9 flex items-center gap-2 rounded-md border border-input bg-background px-3 text-sm text-muted-foreground hover:text-foreground transition-colors">
      {% icon "search" 16 %}
      <span class="flex-1 text-left">Search...</span>
      <kbd class="hidden sm:inline-flex h-5 items-center rounded border border-border bg-muted px-1.5 text-[10px] font-mono text-muted-foreground">
        <span class="mr-0.5">⌘</span>K
      </kbd>
    </button>
  </div>

  <div class="flex items-center gap-2">
    <button type="button"
            aria-label="Notifications"
            class="relative h-9 w-9 rounded-md border border-border inline-flex items-center justify-center hover:bg-accent">
      {% icon "bell" 18 %}
      <span class="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-destructive ring-2 ring-card"></span>
    </button>
    <button type="button"
            aria-label="Toggle theme"
            @click="toggleTheme()"
            class="h-9 w-9 rounded-md border border-border inline-flex items-center justify-center hover:bg-accent">
      {% icon "sun" 18 %}
    </button>

    {% if user.is_authenticated %}
      {% include "partials/nav_user_menu.html" %}
    {% endif %}
  </div>
</header>
```

Note: `@click="toggleTheme()"` on the theme button replaces the old inline `x-data="{}"` dance — now it uses the root shell's method. That's nicer.

- [ ] **Step 6.2 — Create empty `nav_user_menu.html` placeholder**

Create `templates/partials/nav_user_menu.html`:
```html
{# Populated in Task 7. #}
<span></span>
```

This keeps the header rendering while Task 7 builds the real dropdown.

- [ ] **Step 6.3 — Verify page renders without 500**

Run: `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/accounts/login/`
Expected: `200`. (Login page uses auth layout, not dashboard — still validates base.html chain.)

---

## Task 7 — Nav-user dropdown

**Files:**
- Modify: `templates/partials/nav_user_menu.html`

- [ ] **Step 7.1 — Build the dropdown**

Overwrite `templates/partials/nav_user_menu.html`:
```html
{% load apex %}
<div x-data="{ open: false }"
     @click.outside="open = false"
     @keydown.escape="open = false"
     class="relative">
  <button type="button"
          @click="open = !open"
          :aria-expanded="open"
          aria-haspopup="menu"
          class="h-9 flex items-center gap-2 rounded-md hover:bg-accent px-2">
    {% if user.avatar %}
      <img src="{{ user.avatar.url }}" alt="" class="h-7 w-7 rounded-full object-cover" />
    {% else %}
      <span class="h-7 w-7 rounded-full inline-flex items-center justify-center text-xs font-semibold text-white"
            style="background-color: {{ user|avatar_color }};">{{ user|initials }}</span>
    {% endif %}
    <span class="hidden sm:inline text-sm font-medium">{{ user.username }}</span>
    {% icon "chevron-down" 14 "text-muted-foreground" %}
  </button>

  <div x-show="open"
       x-cloak
       x-transition
       role="menu"
       class="absolute right-0 mt-2 w-56 rounded-md border border-border bg-popover text-popover-foreground shadow-lg overflow-hidden"
       style="display: none;">
    <div class="px-3 py-2.5 border-b border-border">
      <div class="text-sm font-medium truncate">{{ user.get_full_name|default:user.username }}</div>
      <div class="text-xs text-muted-foreground truncate">{{ user.email|default:user.username }}</div>
    </div>
    <ul class="py-1 text-sm" role="none">
      <li role="none">
        <a role="menuitem" href="{% url 'settings:profile' %}"
           class="flex items-center gap-2 px-3 py-2 hover:bg-accent hover:text-accent-foreground">
          {% icon "user" 14 "text-muted-foreground" %}
          <span>Profile</span>
        </a>
      </li>
      <li role="none">
        <a role="menuitem" href="{% url 'settings:profile' %}"
           class="flex items-center gap-2 px-3 py-2 hover:bg-accent hover:text-accent-foreground">
          {% icon "settings" 14 "text-muted-foreground" %}
          <span>Settings</span>
        </a>
      </li>
    </ul>
    <div class="border-t border-border">
      <form method="post" action="{% url 'logout' %}">
        {% csrf_token %}
        <button type="submit"
                role="menuitem"
                class="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground">
          {% icon "log-out" 14 "text-muted-foreground" %}
          <span>Sign out</span>
        </button>
      </form>
    </div>
  </div>
</div>
```

- [ ] **Step 7.2 — Re-run full unit suite**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `88 passed`.

- [ ] **Step 7.3 — Smoke-test the server**

Run (needs login session — just check login page is still up):
`curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/accounts/login/`
Expected: `200`.

- [ ] **Step 7.4 — Visual verification**

Re-run the polish-tour screenshot script:
```
/Users/silkalns/.local/bin/uv run python /tmp/apex-compare/polish-tour.py 2>&1 | tail -3
```

Expected: `ok`. Screenshots will land in `/tmp/apex-compare/polish/`.

Use `sips -Z 1800` to resize a few key ones and view via Read:
```
sips -Z 1800 /tmp/apex-compare/polish/light-dashboard.png --out /tmp/apex-compare/polish-small/light-dashboard.png >/dev/null
```
Then Read `/tmp/apex-compare/polish-small/light-dashboard.png`. Confirm:
- ⌘K chip appears on right of the search box in header
- Hamburger icon visible only under lg (take a mobile-sized shot if possible, or resize in DevTools)
- Avatar dropdown chevron visible next to username

---

## Task 8 — E2E tests for the shell

**Files:**
- Create: `tests/e2e/test_shell.py`

- [ ] **Step 8.1 — Write the failing E2E tests**

```python
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="demo1234"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_command_palette_opens_with_cmd_k(page, server_url):
    _login(page, server_url)
    page.keyboard.press("Meta+k")
    page.wait_for_selector('input#palette-input', state='visible', timeout=2000)
    assert page.is_visible('input#palette-input')


def test_command_palette_filters_and_navigates(page, server_url):
    _login(page, server_url)
    page.keyboard.press("Meta+k")
    page.wait_for_selector('input#palette-input', state='visible')
    page.fill("#palette-input", "ord")
    # Enter activates the top match (Orders)
    page.keyboard.press("Enter")
    page.wait_for_url(f"{server_url}/orders/", timeout=3000)


def test_nav_user_dropdown_signs_out(page, server_url):
    _login(page, server_url)
    # The dropdown trigger contains the username; click it.
    page.click('header button:has-text("demo")')
    page.wait_for_selector('role=menuitem >> text=Sign out', state='visible', timeout=2000)
    page.click('role=menuitem >> text=Sign out')
    page.wait_for_url(f"{server_url}/accounts/login/", timeout=3000)


def test_mobile_drawer_opens_with_hamburger(page, server_url):
    page.set_viewport_size({"width": 400, "height": 800})
    _login(page, server_url)
    # Hamburger only visible under lg; clicking opens the aside
    page.click('button[aria-label="Open menu"]')
    # Sidebar is `translate-x-0` when drawer.open is true — Playwright measures final position
    sidebar = page.locator('aside[aria-label="Sidebar"]')
    box = sidebar.bounding_box()
    assert box is not None and box["x"] >= 0, f"Sidebar should be on-screen when drawer open, got x={box}"
    # Close with the X
    page.click('aside[aria-label="Sidebar"] button[aria-label="Close menu"]')
    # Wait for transition
    page.wait_for_timeout(300)
    box2 = sidebar.bounding_box()
    assert box2 is None or box2["x"] < 0, f"Sidebar should be off-screen after close, got x={box2}"
```

- [ ] **Step 8.2 — Run the E2E tests**

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_shell.py -m e2e -v 2>&1 | tail -30`
Expected: all 4 pass. If any fail:
- Palette-open failures → check `shell.js` is loaded (`curl http://127.0.0.1:8000/static/js/shell.js`)
- Dropdown failures → selector may need tuning; inspect with `--headed` via `PWDEBUG=1`
- Drawer failure → check Alpine `x-show` and Tailwind classes are in the built CSS

If tests fail, iterate until they pass. Don't proceed to Task 9.

---

## Task 9 — Commit the shell changes

- [ ] **Step 9.1 — Verify clean state**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -q 2>&1 | tail -3 && /Users/silkalns/.local/bin/uv run pytest tests/e2e/test_shell.py -m e2e -q 2>&1 | tail -3`

Expected:
- Unit: `88 passed`
- E2E: `4 passed`

- [ ] **Step 9.2 — Review diff**

Run: `git status && git diff --stat`

Expected files in the diff:
- New: `apps/core/navigation.py`, `apps/core/tests/test_navigation.py`, `static/js/shell.js`, `templates/partials/command_palette.html`, `templates/partials/nav_user_menu.html`, `templates/partials/breadcrumbs.html` (stub), `tests/e2e/test_shell.py`
- Modified: `apps/core/context_processors.py`, `apps/core/templatetags/apex.py` (icons only), `apps/core/tests/test_nav.py`, `templates/base.html`, `templates/layouts/dashboard.html`, `templates/partials/sidebar.html`, `templates/partials/header.html`, `static_src/css/input.css`, `static/css/app.css` (built artifact)

- [ ] **Step 9.3 — Commit**

```bash
git add apps/core/navigation.py apps/core/tests/test_navigation.py apps/core/context_processors.py apps/core/templatetags/apex.py apps/core/tests/test_nav.py static/js/shell.js static_src/css/input.css static/css/app.css templates/base.html templates/layouts/dashboard.html templates/partials/sidebar.html templates/partials/header.html templates/partials/command_palette.html templates/partials/nav_user_menu.html templates/partials/breadcrumbs.html tests/e2e/test_shell.py
git commit -m "$(cat <<'EOF'
feat(core): shell chrome upgrade — palette, drawer, user menu

- Central nav module at apps/core/navigation.py (single source for
  sidebar + command palette)
- Command palette (⌘K / Ctrl+K) with substring match on label + keywords
- Mobile sidebar drawer with hamburger, backdrop, close-X
- Header nav-user dropdown (profile, settings, sign out)
- Search input becomes palette trigger with ⌘K hint
- Shared Alpine state via apexShell() factory on the dashboard layout
- 4 E2E tests (palette, filter + navigate, sign out, mobile drawer)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10 — BreadcrumbsMixin module

**Files:**
- Create: `apps/core/breadcrumbs.py`
- Create: `apps/core/tests/test_breadcrumbs.py`

- [ ] **Step 10.1 — Write failing test**

`apps/core/tests/test_breadcrumbs.py`:
```python
import pytest
from django.test import RequestFactory
from django.views.generic import TemplateView

from apps.core.breadcrumbs import BreadcrumbsMixin

pytestmark = pytest.mark.django_db


def _dispatch(view_cls, path="/"):
    view = view_cls()
    view.request = RequestFactory().get(path)
    return view


def test_single_level_breadcrumb_includes_dashboard_root_and_current():
    class OrdersListView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Orders"

    view = _dispatch(OrdersListView, "/orders/")
    crumbs = view.get_breadcrumbs()
    assert crumbs == [("Dashboard", "/"), ("Orders", None)]


def test_nested_breadcrumb_walks_parent():
    class OrderEditView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Edit order"
        breadcrumb_parent = "orders:list"

    view = _dispatch(OrderEditView, "/orders/5/edit/")
    crumbs = view.get_breadcrumbs()
    assert crumbs == [
        ("Dashboard", "/"),
        ("Orders", "/orders/"),
        ("Edit order", None),
    ]


def test_get_context_data_injects_breadcrumbs():
    class OrdersListView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_title = "Orders"

    view = _dispatch(OrdersListView)
    ctx = view.get_context_data()
    assert ctx["breadcrumbs"][0] == ("Dashboard", "/")
    assert ctx["breadcrumbs"][-1] == ("Orders", None)


def test_dynamic_title_via_override():
    class OrderDetailView(BreadcrumbsMixin, TemplateView):
        template_name = "dummy.html"
        breadcrumb_parent = "orders:list"

        def get_breadcrumb_title(self):
            return "ORD-00042"

    view = _dispatch(OrderDetailView)
    crumbs = view.get_breadcrumbs()
    assert crumbs[-1] == ("ORD-00042", None)
```

- [ ] **Step 10.2 — Verify it fails**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_breadcrumbs.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError: No module named 'apps.core.breadcrumbs'`

- [ ] **Step 10.3 — Implement `apps/core/breadcrumbs.py`**

```python
from typing import Any
from django.urls import reverse


class BreadcrumbsMixin:
    """Class-based view mixin that injects a `breadcrumbs` context variable.

    Each view declares:
      - breadcrumb_title: str           (override get_breadcrumb_title for dynamic)
      - breadcrumb_parent: str | tuple[str, str] | None
          URL name of the parent view, or (title, url_name) when the parent
          label should differ from the NAV_ITEMS label (rare).

    The result is a list of (title, href_or_None) tuples; href is None for
    the current (last) crumb.
    """

    breadcrumb_title: str | None = None
    breadcrumb_parent: str | tuple[str, str] | None = None

    def get_breadcrumb_title(self) -> str:
        return self.breadcrumb_title or ""

    def get_breadcrumbs(self) -> list[tuple[str, str | None]]:
        crumbs: list[tuple[str, str | None]] = [("Dashboard", reverse("dashboard"))]
        parent = self.breadcrumb_parent
        if parent:
            if isinstance(parent, tuple):
                title, url_name = parent
            else:
                title, url_name = self._resolve_parent_title(parent), parent
            crumbs.append((title, reverse(url_name)))
        crumbs.append((self.get_breadcrumb_title(), None))
        return crumbs

    @staticmethod
    def _resolve_parent_title(url_name: str) -> str:
        from apps.core.navigation import NAV_ITEMS
        for item in NAV_ITEMS:
            if item.url_name == url_name:
                return item.label
        return url_name.split(":")[-1].replace("_", " ").title()

    def get_context_data(self, **kwargs: Any) -> dict:
        ctx = super().get_context_data(**kwargs) if hasattr(super(), "get_context_data") else {}
        ctx["breadcrumbs"] = self.get_breadcrumbs()
        return ctx
```

- [ ] **Step 10.4 — Verify tests pass**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_breadcrumbs.py -v 2>&1 | tail -10`
Expected: 4 passed.

---

## Task 11 — Breadcrumbs templatetag + partial

**Files:**
- Modify: `apps/core/templatetags/apex.py` (add inclusion tag)
- Modify: `templates/partials/breadcrumbs.html` (replace stub)
- Modify: `apps/core/tests/test_breadcrumbs.py` (add tag test)

- [ ] **Step 11.1 — Add template tag**

In `apps/core/templatetags/apex.py`, at the bottom of the file append:
```python
@register.inclusion_tag("partials/breadcrumbs.html", takes_context=False)
def breadcrumbs(crumbs):
    """Render the breadcrumb bar; returns empty if fewer than 2 crumbs."""
    crumbs = list(crumbs or [])
    return {"crumbs": crumbs if len(crumbs) >= 2 else []}
```

- [ ] **Step 11.2 — Implement the partial**

Overwrite `templates/partials/breadcrumbs.html`:
```html
{% load apex %}
{% if crumbs %}
<nav aria-label="Breadcrumb" class="w-full border-b border-border bg-card/30">
  <ol class="flex items-center gap-1.5 h-10 px-4 lg:px-6 text-sm text-muted-foreground">
    {% for title, href in crumbs %}
      <li class="flex items-center gap-1.5">
        {% if href %}
          <a href="{{ href }}" class="hover:text-foreground transition-colors">{{ title }}</a>
        {% else %}
          <span class="text-foreground font-medium" aria-current="page">{{ title }}</span>
        {% endif %}
        {% if not forloop.last %}
          <span class="text-muted-foreground/50">{% icon "chevron-right" 14 %}</span>
        {% endif %}
      </li>
    {% endfor %}
  </ol>
</nav>
{% endif %}
```

- [ ] **Step 11.3 — Wire tag into layout**

Open `templates/layouts/dashboard.html`. Replace:
```html
    {% include "partials/breadcrumbs.html" %}
```
with:
```html
    {% breadcrumbs breadcrumbs %}
```

Then at the top of the layout (with other `{% load %}`s), ensure `{% load apex %}` is already there (it is).

- [ ] **Step 11.4 — Add tag unit test**

Append to `apps/core/tests/test_breadcrumbs.py`:
```python
from django.template.loader import render_to_string


def test_breadcrumbs_tag_renders_nothing_for_single_crumb():
    html = render_to_string("partials/breadcrumbs.html", {"crumbs": []})
    assert "<nav" not in html


def test_breadcrumbs_tag_renders_all_crumbs():
    html = render_to_string("partials/breadcrumbs.html", {
        "crumbs": [("Dashboard", "/"), ("Orders", "/orders/"), ("ORD-5", None)],
    })
    assert "Dashboard" in html and "/orders/" in html
    assert 'aria-current="page"' in html
    assert "ORD-5" in html
```

- [ ] **Step 11.5 — Run tests**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_breadcrumbs.py -v 2>&1 | tail -10`
Expected: 6 passed.

---

## Task 12 — View sweep (static titles)

**Files:**
- Modify: `apps/dashboard/views.py`
- Modify: `apps/orders/views.py`
- Modify: `apps/products/views.py`
- Modify: `apps/accounts/views.py`

- [ ] **Step 12.1 — Dashboard view**

`apps/dashboard/views.py` — `DashboardView` does not use `get_context_data` (it uses `get` directly with `render(...)`). Add breadcrumbs to the render context. Modify the final `render(...)` call:
```python
        return render(request, "dashboard/index.html", {
            "stats": stats,
            "traffic_sources": traffic_sources,
            "goals": goals,
            "recent_orders": recent_orders,
            "activities": activities,
            "breadcrumbs": [("Dashboard", None)],  # single crumb → tag renders nothing
        })
```

Rationale: Dashboard is the root, so no breadcrumbs bar shows (by design). Providing the key keeps templates consistent.

- [ ] **Step 12.2 — Orders views**

`apps/orders/views.py` — add `BreadcrumbsMixin` import and class attrs:
```python
from apps.core.breadcrumbs import BreadcrumbsMixin
```

Modify each view:
```python
class OrderListView(BreadcrumbsMixin, LoginRequiredMixin, ListView):
    ...
    breadcrumb_title = "Orders"

class OrderDetailView(BreadcrumbsMixin, LoginRequiredMixin, DetailView):
    ...
    breadcrumb_parent = "orders:list"

    def get_breadcrumb_title(self):
        return self.object.number

class OrderCreateView(BreadcrumbsMixin, LoginRequiredMixin, CreateView):
    ...
    breadcrumb_title = "New order"
    breadcrumb_parent = "orders:list"

class OrderUpdateView(BreadcrumbsMixin, LoginRequiredMixin, UpdateView):
    ...
    breadcrumb_parent = "orders:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.number}"
```

MRO note: put `BreadcrumbsMixin` FIRST so its `get_context_data` calls `super().get_context_data()` which flows through `LoginRequiredMixin` (pass-through) → the generic view's implementation.

- [ ] **Step 12.3 — Products views**

`apps/products/views.py`:
```python
from apps.core.breadcrumbs import BreadcrumbsMixin


class ProductListView(BreadcrumbsMixin, LoginRequiredMixin, ListView):
    ...
    breadcrumb_title = "Products"


class ProductDetailView(BreadcrumbsMixin, LoginRequiredMixin, DetailView):
    ...
    breadcrumb_parent = "products:list"

    def get_breadcrumb_title(self):
        return self.object.name


class ProductCreateView(BreadcrumbsMixin, LoginRequiredMixin, CreateView):
    ...
    breadcrumb_title = "New product"
    breadcrumb_parent = "products:list"


class ProductUpdateView(BreadcrumbsMixin, LoginRequiredMixin, UpdateView):
    ...
    breadcrumb_parent = "products:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.name}"
```

- [ ] **Step 12.4 — Accounts views (users + profile)**

`apps/accounts/views.py` — find all CBVs. Add mixin + attrs:

Read the file first to see which class names to edit:
```
grep -n "class.*View" apps/accounts/views.py
```

Expected classes (approx): `RegisterView`, `UserListView`, `UserDetailView`, `UserCreateView`, `UserUpdateView`, `ProfileView`.

Apply:
- `UserListView`: `breadcrumb_title = "Users"`
- `UserDetailView`: `breadcrumb_parent = "users:list"`, dynamic title = `self.object.username`
- `UserCreateView`: `breadcrumb_title = "New user"`, `breadcrumb_parent = "users:list"`
- `UserUpdateView`: `breadcrumb_parent = "users:list"`, dynamic title = `f"Edit {self.object.username}"`
- `ProfileView`: `breadcrumb_title = "Settings"`
- `RegisterView`: skip (uses auth layout, no breadcrumbs)

- [ ] **Step 12.5 — Run unit suite**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `92 passed` (88 + 4 breadcrumb tests) or similar.

- [ ] **Step 12.6 — Manual smoke — curl a page that should now have breadcrumbs**

With demo session cookie — simpler to just check the HTML of the login-free path. Actually these views are all LoginRequired, so we'd need to log in. Instead, verify via re-screenshot:
```
/Users/silkalns/.local/bin/uv run python /tmp/apex-compare/polish-tour.py 2>&1 | tail -3
sips -Z 1800 /tmp/apex-compare/polish/light-orders-list.png --out /tmp/apex-compare/polish-small/light-orders-list.png >/dev/null
```
Read the resized screenshot. Confirm a breadcrumb row reads `Dashboard / Orders` under the header.

---

## Task 13 — E2E breadcrumbs test

**Files:**
- Modify: `tests/e2e/test_shell.py`

- [ ] **Step 13.1 — Add the breadcrumbs test**

Append to `tests/e2e/test_shell.py`:
```python
def test_breadcrumbs_on_order_detail(page, server_url):
    _login(page, server_url)
    # The seed creates 30 orders — grab the first one from the list
    page.goto(f"{server_url}/orders/")
    page.wait_for_selector("table")
    # Click the first order detail link (number column)
    page.click("table tbody tr a, table tbody tr td a")
    # Wait for detail page
    page.wait_for_selector("nav[aria-label='Breadcrumb']", timeout=3000)
    crumbs_text = page.locator("nav[aria-label='Breadcrumb']").inner_text()
    assert "Dashboard" in crumbs_text
    assert "Orders" in crumbs_text


def test_palette_excludes_staff_only_for_non_staff(page, server_url):
    """demo user has is_staff=False per seed_demo; Users page must not appear in palette."""
    _login(page, server_url)
    page.keyboard.press("Meta+k")
    page.wait_for_selector('input#palette-input', state='visible')
    page.fill("#palette-input", "users")
    # If any button with label "Users" shows up, it's a staff leak
    count = page.locator('div[role="dialog"] button:has-text("Users")').count()
    assert count == 0, "palette leaked staff-only Users page to non-staff user"
```

**Pre-check:** does `seed_demo` create demo as `is_staff=False`? Grep to confirm:
```
grep -n "is_staff" apps/core/management/commands/seed_demo.py
```
If demo is `is_staff=True`, the second test needs a separate non-staff user fixture, or skip the test with a note.

- [ ] **Step 13.2 — Run E2E**

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_shell.py -m e2e -v 2>&1 | tail -30`
Expected: 6 passed.

If the first-order-link selector is brittle, inspect the orders list template and pick a more specific locator (e.g., `table tbody tr:first-child td:first-child a`).

---

## Task 14 — Commit the breadcrumbs changes

- [ ] **Step 14.1 — Full verification**

Run:
```
/Users/silkalns/.local/bin/uv run pytest apps/ -q 2>&1 | tail -3
/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3
```
Expected:
- Unit: all passing (92+ tests)
- E2E: 6 passed in `test_shell.py`

- [ ] **Step 14.2 — Commit**

```bash
git add apps/core/breadcrumbs.py apps/core/tests/test_breadcrumbs.py apps/core/templatetags/apex.py apps/dashboard/views.py apps/orders/views.py apps/products/views.py apps/accounts/views.py templates/layouts/dashboard.html templates/partials/breadcrumbs.html tests/e2e/test_shell.py
git commit -m "$(cat <<'EOF'
feat(core): breadcrumbs across dashboard views

- BreadcrumbsMixin for class-based views with static or dynamic titles
- {% breadcrumbs %} inclusion tag (renders nothing for <2 crumbs)
- Breadcrumb bar slots under the header in the dashboard layout
- View sweep: orders, products, users, settings — list/detail/create/edit
- 2 E2E tests: trail on order detail, palette staff gate

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 14.3 — Visual re-shoot for the record**

```
/Users/silkalns/.local/bin/uv run python /tmp/apex-compare/polish-tour.py 2>&1 | tail -3
```
Confirm screenshots look correct.

---

## Done — Phase 1 complete

Summary:
- 2 commits
- +7 new files, ~10 modified
- ~+10 unit tests, +6 E2E tests
- All 6 shell features shipped

Next up: Phase 2 — settings expansion (profile / password / appearance / two-factor tabs). That's a separate brainstorm + spec + plan cycle.
