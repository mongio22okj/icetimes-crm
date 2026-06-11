# Phase 10 — Component Library

**Date:** 2026-04-29
**Status:** Draft
**Scope:** A first-class `/components/` surface that documents every reusable UI primitive shipped with Apex. Closes the biggest perceived gap vs. Metronic / TailAdmin Pro / Material Tailwind: not enough documented primitives.

## Context

Per [phases 10–19 roadmap](2026-04-29-phase10-19-roadmap.md#phase-10--component-library) — reviewers and buyers grade dashboard kits by scrolling a components page. Apex currently has a "Widgets gallery" and "Forms gallery" but no primitives reference (modals, toasts, drawers, tabs, accordions, datepickers, etc.). This phase ships them and makes them copy-paste discoverable.

## Goals

- Every primitive listed below renders in at least one canonical variant on a documented page.
- Each demo page shows the primitive *and* its underlying markup via the existing `_codeblock.html`.
- All primitives work keyboard-only, respect `prefers-reduced-motion`, and pass an axe-core check.
- Toast notifications are wired into Django's messages framework so existing views automatically light them up.

## Non-goals

- WYSIWYG / rich-text editor (lives in [Phase 12 — Forms 2.0](#)).
- Chart components (already covered by Phase 8 charts showcase).
- Drag-to-reorder primitives (no kanban-style sortable in this phase — kanban already has its own).
- Theme builder UI (palette is edited in CSS; phase out of scope).
- Marketing-site landing components (live in `apps/marketing`, separate concern).

## Features

### Primitives shipped

Grouped by category; each primitive has its own page under `/components/<slug>/`.

| Group | Primitive | Variants |
|---|---|---|
| **Overlay** | Modal | sm, md, lg, full-screen, with-form, scrollable-body, danger-confirm |
| | Drawer | left, right, bottom, with-tabs |
| | Toast | info, success, warning, error, with-action, persistent |
| | Tooltip | top/right/bottom/left, click-trigger, keyboard-trigger |
| | Popover | menu, info, with-form |
| **Disclosure** | Tabs | underline, pill, vertical, with-badges |
| | Accordion | single-open, multi-open, with-icons, faq-style |
| | Stepper | horizontal-numbered, vertical, with-progress, completed/active/pending states |
| **Inputs (preview only — Phase 12 builds the real widgets)** | Datepicker | single, with-shortcuts |
| | Daterange | side-by-side, presets |
| | Timepicker | 12h, 24h |
| | Color picker | swatches, hex input |
| **Choice** | Multi-select | tag-style, dropdown-with-checkboxes |
| | Tag input | free-form, with-suggestions |
| | Combobox | typeahead, async |
| | Toggle group | single, multiple |
| | Segmented control | 2/3/4 segments |
| | Rating | stars, hearts |
| | Slider | single, range |
| **Upload** | File dropzone | single, multi, image-preview, with-progress |
| **Feedback** | Skeleton | text, card, table-row, avatar |
| | Spinner | sm, md, lg, with-label |
| | Progress ring | sm, md, lg, with-label |
| | Empty state | no-data, no-results, no-permission, error, success, first-run |
| **Identity** | Avatar | initials, image, with-status, group-stack |
| | Badge | variants × density × shape (pill / square) |

Total: ~26 primitives, ~120 documented variants.

### Page structure

Each component page follows the same template:

1. **Heading + 1-line description.**
2. **Live demo** — primary canonical variant, interactive.
3. **Variants grid** — 3–8 secondary variants, each with a label.
4. **Usage** — markup snippet via `_codeblock.html`.
5. **Accessibility notes** — keyboard nav, ARIA roles, focus management.
6. **Anatomy diagram** (optional, for complex primitives like Modal / Tabs).

### Index page (`/components/`)

Grid of primitive cards (icon + name + 1-line description) grouped by category. Acts as the entry point. Searchable via the existing command palette (each primitive registered as a `NavItem` keyword target).

### Toast → Django messages bridge

`apps/core/messages.py` exposes a `toast(request, level, body, *, action=None, persistent=False)` helper that pushes onto `messages.add_message` with extra metadata in `extra_tags`. The base layout renders an Alpine-powered `<div x-data="apexToasts()">` that drains `messages` on each request and auto-dismisses after 5s. Existing `messages.success(...)` calls light up automatically.

## Architecture

### URLs

```text
apex/urls.py adds:
  /components/    → apps.components.urls

apps/components/urls.py:
  ""                       ComponentIndexView   (grid of all primitives)
  "<slug:primitive>/"      ComponentDetailView  (renders primitive's demo page)
```

`primitive` slug maps to a registry entry; missing slugs 404.

### App layout

```text
apps/components/
├── apps.py
├── registry.py          PRIMITIVES tuple — one entry per primitive
├── views.py             ComponentIndexView, ComponentDetailView
├── urls.py
├── tests/
│   ├── test_views.py
│   └── test_registry.py
└── templatetags/
    └── components.py    {% component_demo "modal" %} renders the page

templates/components/
├── _index.html          (the grid)
├── _detail.html         (shared layout for any primitive page)
├── _variant.html        (single variant card with label + body)
├── primitives/
│   ├── modal.html       (the actual primitive markup, includable via {% include %})
│   ├── drawer.html
│   ├── toast.html
│   ├── ...
└── pages/
    ├── modal.html       (the demo page rendered at /components/modal/)
    ├── drawer.html
    └── ...
```

### Registry shape

```python
# apps/components/registry.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Primitive:
    slug: str
    label: str
    category: str       # "overlay" | "disclosure" | "inputs" | "choice" | "upload" | "feedback" | "identity"
    icon: str           # lucide icon name
    description: str    # 1-line for the index card

PRIMITIVES: tuple[Primitive, ...] = (
    Primitive("modal", "Modal", "overlay", "square-stack", "Centered dialog with backdrop and focus trap."),
    Primitive("drawer", "Drawer", "overlay", "panel-right", "Slide-in panel from any edge."),
    # ... ~26 entries total
)
```

`ComponentIndexView` groups by `category`; `ComponentDetailView` looks up the slug, 404s otherwise, and renders `templates/components/pages/<slug>.html`.

### JS additions

All Alpine-based, no new heavy deps.

- `static/js/components.js` — Alpine `data()` factories: `apexModal()`, `apexDrawer()`, `apexToasts()`, `apexTabs()`, `apexAccordion()`, `apexCombobox()`, `apexTagInput()`, `apexFileDropzone()`. Each is a small (10–40 LOC) factory mirroring the patterns already in `static/js/shell.js`.
- Loaded via a single `<script src="{% static 'js/components.js' %}" defer>` in `base.html` (next to `shell.js`).
- No date library — datepicker is a thin Alpine wrapper over `<input type="date">` with a custom popover for shortcuts. Phase 12 may upgrade to a richer picker.

### Toast bridge

```python
# apps/core/messages.py
from django.contrib import messages

LEVEL_TO_TAG = {
    messages.SUCCESS: "success",
    messages.ERROR: "error",
    messages.WARNING: "warning",
    messages.INFO: "info",
    messages.DEBUG: "info",
}

def toast(request, level, body, *, action=None, persistent=False):
    extra = LEVEL_TO_TAG[level]
    if persistent:
        extra += " persistent"
    if action:
        extra += f" action::{action['label']}::{action['url']}"
    messages.add_message(request, level, body, extra_tags=extra)
```

Template in `partials/toasts.html` (included once from `layouts/dashboard.html`):

```html
<div x-data="apexToasts({{ messages|json_script_safe }})" ...>
  <template x-for="t in toasts" :key="t.id">
    <div class="..." :class="t.classes" @click="dismiss(t.id)">...</div>
  </template>
</div>
```

### Sidebar nav

One new top-level `NavItem` in `apps/core/navigation.py`:

```python
NavItem(_("Components"), "components:index", "blocks",
        keywords=("components", "primitives", "ui", "library"),
        group=G_SHOWCASE, requires_staff=True),
```

Individual primitives **don't** get nav entries (would explode the sidebar). They're discoverable via the index page and command-palette keyword search (we register a synthetic palette section in Phase 10 follow-up if needed; for now the index entry suffices).

### Accessibility baseline

Every primitive page documents:
- **Keyboard map** (Tab/Shift+Tab/Enter/Esc/Arrow keys).
- **ARIA roles + attributes** used.
- **Focus management** (e.g. modal returns focus to trigger on close).
- **Reduced-motion** behaviour (animations disabled when `@media (prefers-reduced-motion: reduce)`).

Add a single `_a11y_panel.html` partial that renders these from a structured dict on the registry entry, so authors don't write boilerplate.

## Testing

### Unit (~12 new tests)

- Registry: every entry has unique slug, valid category, non-empty description.
- ComponentIndexView: 200 for staff, 302 for anonymous (requires_staff), groups primitives by category.
- ComponentDetailView: 200 for known slug, 404 for unknown slug, template path matches `pages/<slug>.html`.
- `toast()` helper: pushes message with correct extra_tags for each level + persistent flag + action.

### E2E (~5 new tests, marked `e2e`)

- `/components/` index renders all category headers and at least 20 primitive cards.
- Open Modal demo, click trigger, assert backdrop visible + Esc closes + focus restored.
- Open Drawer demo (right variant), assert slide-in animation completes + click outside closes.
- Toast: trigger demo button, assert toast appears, auto-dismisses after 5s.
- Tabs: click each tab, assert correct panel visible + keyboard arrow nav works.

### Visual regression (manual, captured into screenshots/)

Screenshots committed for: index page, modal demo, drawer demo, toast demo, tabs demo, accordion demo, datepicker demo, multi-select demo, file dropzone demo, empty-state variants, avatars demo. ~12 new screenshots.

## Rollout — 7 commits

1. **docs** — this spec, screenshots placeholder list.
2. **scaffolding** — `apps/components/` skeleton (registry, views, urls, base templates, nav entry, index page, single-primitive smoke test).
3. **overlay group** — modal, drawer, toast (incl. messages bridge), tooltip, popover + their JS factories + tests.
4. **disclosure group** — tabs, accordion, stepper + tests.
5. **choice group** — multi-select, tag input, combobox, toggle group, segmented control, rating, slider + JS factories + tests.
6. **input/upload/feedback/identity groups** — datepicker, daterange, timepicker, color picker, file dropzone, skeleton, spinner, progress ring, empty states, avatars, badges + tests.
7. **polish + screenshots + E2E** — axe-core sweep, reduced-motion check, all screenshots, the 5 E2E tests, README/CHANGELOG entries.

## Branch + parent

- Branch: `phase10-components`
- Parent: current main-of-PRs branch (whatever phase 9 i18n merged into).

## Open questions

- Should the toast container live in `layouts/dashboard.html` only, or also in `layouts/auth.html` and `layouts/public.html`? Probably dashboard + public; auth pages rarely need toasts beyond Django's own form errors.
- Do we ship a "code copy" button on snippets in this phase or defer to Phase 18 (marketing polish)? Suggest: ship now, it's 15 LOC of clipboard JS.
- File dropzone: hand-roll vs. small dep (e.g. `dropzone-mini`)? Suggest: hand-roll a 60-LOC vanilla version; we control bundling and accessibility.
