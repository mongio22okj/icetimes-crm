# Apex Parity Roadmap — Phases 4b → 9

> **For agentic workers:** This is a **roadmap**, not a task-level plan. Each phase listed here still needs its own brainstorm → spec → plan cycle before implementation, following the pattern established in [Phase 4a](2026-04-23-phase4a-customers.md). Do not treat phases below as ready-to-execute.

**Goal:** Reach visual + functional parity with the original [Apex Next.js/React dashboard](https://apex-dashboard.pages.dev) while preserving the Django-native, server-rendered, no-SPA architecture.

**Definition of parity:** For each surface in the reference app, a Django equivalent exists that (a) renders the same information architecture, (b) supports the same primary user actions, and (c) matches the design tokens / layout to the same degree as existing phases. "Pixel-perfect" is **not** a goal — the port uses Tailwind v4 + Alpine + HTMX, not React + Recharts.

**Tech stack constraint (hard):** No new SPA framework. All new work continues to use Django 5.1 · Tailwind v4 · Alpine.js · HTMX · ApexCharts. New Python/JS deps may be added only when existing stack cannot cover the feature (documented per-phase).

---

## Current state (2026-04-24)

Completed phases on `main` + `phase4a-customers`:

| Phase | Surface | Status |
|---|---|---|
| MVP (Phase 1) | Scaffold, Dashboard, Auth, Users, Products, Orders, Profile, error pages | ✅ v0.1.0 |
| Phase 1 — Shell & Chrome | Command palette, breadcrumbs, mobile drawer, nav-user dropdown | ✅ |
| Phase 2 — Settings + 2FA | Tabbed settings, Appearance picker, TOTP 2FA + recovery codes | ✅ |
| Phase 3 — Auth completion | Verify-email, EmailVerifiedRequiredMixin, sudo-mode confirm-password | ✅ |
| Phase 4a — Customers | Customer model + soft-delete CRUD, Order FK swap | ✅ (current branch, ready to merge) |

**Features from the MVP "out of scope" list now complete:** Customers, Two-factor, Command palette, Theme customizer, Verify-email.

---

## Remaining parity surfaces

Derived from the [MVP plan's out-of-scope list](2026-04-20-apex-django-port-mvp.md#out-of-scope) minus items already shipped, plus the README roadmap:

**Data-heavy CRUD:** Invoices
**Messaging:** Notifications · Mail · Chat
**Productivity apps:** Calendar · Kanban · Files
**Marketing/public:** Analytics landing · SaaS landing · CRM landing · eCommerce landing · Pricing · Support
**UX patterns:** Wizard (multi-step form) · Charts showcase · Lock-screen
**Cross-cutting:** i18n
**Intentionally deferred:** Docs pages (use project README/CHANGELOG instead — not a product surface)

---

## Proposed phase sequence

Phases are grouped by theme and ordered so that shared infrastructure is built before dependents. Each phase is sized to ~4–8 commits — consistent with prior phases — and produces a self-contained, mergeable feature branch.

### Phase 4b — Invoices

**Surface:** Invoice list, detail, create, edit, PDF export, status transitions (draft → sent → paid → overdue → void).
**Rationale:** Closes the commerce CRUD family (Products / Orders / Customers / **Invoices**). Reuses established list/detail/form patterns.
**New deps:** `reportlab` or `weasyprint` for PDF rendering (decide in brainstorm).
**Dependencies:** Phase 4a Customers (invoices are billed to a Customer).
**Estimated size:** 6–8 commits.
**Key decisions for brainstorm:**
- Line-item formset pattern (copy from Orders) vs. HTMX-driven inline add/remove
- PDF template strategy: HTML→PDF (weasyprint) vs. direct reportlab drawing
- Status state machine location: model property vs. `django-fsm`
- Public view token for client-facing invoice URLs (yes/no?)

---

### Phase 4c — Notifications

**Surface:** Header bell dropdown with unread badge, full notifications page, mark-read / mark-all-read, notification preferences tab in Settings.
**Rationale:** Today the header bell is cosmetic. Notifications is foundational infrastructure used by Mail and Chat (unread counts, bell feed), so ship it before those.
**New deps:** None (pure Django model + HTMX polling every 30s; no WebSockets needed for v1).
**Dependencies:** None hard; Phase 2 Settings tabs pattern reused for Notification preferences.
**Estimated size:** 5–6 commits.
**Key decisions for brainstorm:**
- Generic `Notification` model vs. per-sender polymorphic tables
- Polling (HTMX `hx-trigger="every 30s"`) vs. SSE vs. deferring real-time entirely
- Which existing events emit notifications at MVP (e.g., order status change, 2FA recovery code used, verification email sent)

---

### Phase 5a — Mail

**Surface:** Inbox (list), thread view, compose, labels/folders (Inbox/Sent/Drafts/Starred/Trash), star/unstar, mark-read, reply/forward.
**Rationale:** Heaviest "app" surface — exercises the three-pane layout pattern (folder sidebar + list + preview) that Chat and Kanban will also need.
**New deps:** None (Django forms + HTMX for async thread loads). Real SMTP integration is out of scope — uses Django's email backend for send, stores messages in DB.
**Dependencies:** Phase 4c Notifications (new-mail notifications).
**Estimated size:** 7–8 commits.
**Key decisions for brainstorm:**
- Threading model: `parent_message` FK vs. `thread_id` grouping
- Rich-text compose: plain textarea + safe HTML whitelist, or Trix/Quill (adds JS dep)
- Attachments: reuse Files storage from Phase 6c or inline?
- Search: Django `__icontains` for v1 vs. Postgres full-text later

---

### Phase 5b — Chat

**Surface:** Conversations sidebar, message stream, send message, typing indicator, read receipts, 1:1 only (group chat deferred).
**Rationale:** Reuses Mail's three-pane shell and Notification infra. Smaller than Mail since no folders/threads — just conversations.
**New deps:** None (HTMX polling for message stream v1; WebSockets via channels is a deferred enhancement).
**Dependencies:** Phase 4c Notifications, Phase 5a Mail (reuse three-pane layout partials).
**Estimated size:** 5–6 commits.
**Key decisions for brainstorm:**
- Polling interval for message stream (3s? 5s? HTMX SSE?)
- Presence: true presence (online-now tracking) or fake-it-with-last-seen
- Message model: shared with Mail or separate?

---

### Phase 6a — Calendar

**Surface:** Month/week/day views, event create/edit/delete, drag-to-reschedule (stretch), category colors.
**Rationale:** Standalone app; unblocks nothing but closes a major "apps" surface.
**New deps:** FullCalendar v6 (vanilla JS build — no React/Vue wrappers; integrates cleanly with Alpine).
**Dependencies:** None.
**Estimated size:** 5–6 commits.
**Key decisions for brainstorm:**
- FullCalendar event source: JSON endpoint (REST-ish) vs. inline render
- Recurring events: yes (RRULE, adds `python-dateutil` complexity) or no (v1 = single occurrences only)
- Timezone handling: per-user tz in profile vs. UTC only

---

### Phase 6b — Kanban

**Surface:** Board with columns (To Do / In Progress / Done, configurable), cards with title/description/assignee/due date, drag-and-drop between columns.
**Rationale:** Standalone app. Exercises HTMX drag-and-drop pattern usable elsewhere.
**New deps:** SortableJS (vanilla JS, ~40KB) for column DnD. No backend framework changes.
**Dependencies:** None.
**Estimated size:** 5 commits.
**Key decisions for brainstorm:**
- Single global board (MVP) vs. multiple boards per user
- Card position ordering: integer with rebalance, or fractional indexing
- Card detail: modal (HTMX) vs. dedicated page

---

### Phase 6c — Files

**Surface:** File grid/list view, upload (drag-drop + button), folder navigation, rename, delete, share-link (stretch).
**Rationale:** Closes the "apps" surface. Provides attachment storage backend for Mail/Chat if they want it later.
**New deps:** `django-storages` only if cloud storage is targeted; local FileField fine for v1.
**Dependencies:** None.
**Estimated size:** 5–6 commits.
**Key decisions for brainstorm:**
- Folder model: materialized path vs. parent FK (recursive queries)
- Max upload size, allowed types (image/pdf/office docs)
- Preview: PDF.js + image lightbox, or download-only

---

### Phase 7a — Landing variants

**Surface:** Four unauthenticated landing-page variants (Analytics, SaaS, CRM, eCommerce) — hero, features, testimonials, footer. Mostly static content.
**Rationale:** Marketing surface; low dependency, can ship in parallel with any productivity app if resourcing allows.
**New deps:** None.
**Dependencies:** None.
**Estimated size:** 4 commits (one per variant, shared layout partial).
**Key decisions for brainstorm:**
- Single app `apps/marketing/` vs. splat into `apps/core/`
- Content source: hardcoded in templates vs. DB-editable (CMS-lite)
- Hero charts: screenshots vs. live ApexCharts demos

---

### Phase 7b — Pricing + Support

**Surface:** Pricing page (tiers, toggles, FAQ) · Support page (contact form, articles grid, search cosmetic).
**Rationale:** Rounds out the unauthenticated marketing surface.
**New deps:** None.
**Dependencies:** None. Could bundle with 7a if resourcing allows.
**Estimated size:** 3–4 commits.

---

### Phase 8 — UX pattern surfaces

**Surface:**
- **Wizard** — multi-step form pattern (e.g., onboarding flow) with progress bar + step validation
- **Charts showcase** — gallery of every ApexCharts variant (bar/line/pie/area/radial/heatmap) with code snippets
- **Lock-screen** — session-lock page that requires password re-entry (overlays the app, preserves context)

**Rationale:** Low-effort individual pages; bundled because none justifies its own phase.
**New deps:** None.
**Dependencies:** Phase 3 (sudo-mode mixin) for Lock-screen.
**Estimated size:** 4 commits (one per surface + bundle integration).

---

### Phase 9 — i18n

**Surface:** `{% trans %}` / `{% blocktrans %}` pass across every template, `makemessages` / `compilemessages`, language picker in header, at least one non-English locale (e.g., `es` or `de`) stubbed for demo.
**Rationale:** Touches every template, so must be last — otherwise every prior phase has to backfill translations. Parity-critical only if the Apex reference demos locale switching.
**New deps:** None (Django i18n is built-in).
**Dependencies:** All prior phases complete. Running it earlier causes constant retranslation churn.
**Estimated size:** 6–8 commits (one per app + one for shared templates + one for locale files + one for picker).
**Key decisions for brainstorm:**
- Which locales ship in v1 (English + one other, or more?)
- Date/number formatting strategy (Django `L10N` + timezone middleware)
- Dynamic content (Customer names, Order descriptions) — not translated, only chrome

---

## Dependency graph

```text
Phase 4a Customers ──► Phase 4b Invoices
                                   │
Phase 4c Notifications ──┬──► Phase 5a Mail ──► Phase 5b Chat
                         │
                         └──► (bell feed in Phase 1 shell becomes live)

Phase 6a Calendar    (standalone)
Phase 6b Kanban      (standalone)
Phase 6c Files       (standalone — optional input to 5a/5b)

Phase 7a Landings    (standalone)
Phase 7b Pricing/Support (standalone)

Phase 8 UX surfaces  (standalone, Lock-screen depends on Phase 3 sudo-mode)

Phase 9 i18n         ──► MUST come after all chrome-producing phases
```

**Critical path to parity:** 4b → 4c → 5a → 5b → 9. Productivity apps (6a/6b/6c) and marketing (7a/7b) can slot in anywhere and are parallelizable across sessions/agents.

---

## Execution process (per phase)

Follow the pattern established by phases 1–4a:

1. **Brainstorm** — open discussion in chat, identify key decisions (listed above per phase), resolve `Key decisions for brainstorm` items.
2. **Spec** — write `docs/superpowers/specs/YYYY-MM-DD-phaseN-<slug>-design.md` capturing data models, URL structure, template inventory, component contracts, edge cases.
3. **Plan** — write `docs/superpowers/plans/YYYY-MM-DD-phaseN-<slug>.md` with task-by-task breakdown, copy-paste code blocks, test assertions, migration chains — same granularity as [Phase 4a plan](2026-04-23-phase4a-customers.md).
4. **Branch** — `git switch -c phaseN-<slug>` from `main`.
5. **Pre-flight** — baseline unit + E2E suite green before first commit.
6. **Execute** — task-by-task, commit-per-task, `pytest` green at every commit boundary.
7. **E2E sweep** — add Playwright tests covering the primary flow (3–5 tests/phase).
8. **Merge + CHANGELOG** — squash or fast-forward to `main`, append Keep-A-Changelog entry.

---

## Out of scope (even at "parity")

These Apex surfaces are **intentionally skipped** — either because they're deployment concerns rather than product surfaces, or because they conflict with the Django-native architecture:

- **Docs pages** — use project README + CHANGELOG. A separate "Docs" surface inside the app duplicates GitHub/static-site tooling.
- **Real-time via WebSockets** — Mail/Chat/Notifications use HTMX polling. Channels/ASGI is a deferred Phase 10+ concern if real-time latency ever becomes a complaint.
- **Native mobile app** — responsive web only; the Apex Next.js reference is also web-only.
- **Theme customizer drawer (full variant)** — shipped as Appearance tab (Light/Dark/System). A full "pick your accent color" drawer is a future enhancement, not parity.

---

## Risks / tradeoffs

- **Scope creep** — Invoices alone can sprawl into accounting (tax rules, currency, multi-org). **Mitigation:** each phase's spec must enumerate what's *out of scope* explicitly.
- **JS dependency drift** — FullCalendar (6a) and SortableJS (6b) are the first serious vendored JS libs. **Mitigation:** pin versions in `package.json`, vendor via `static_src/vendor/`, no CDN at runtime.
- **i18n churn** — if marketing phases (7a/7b) ship with untranslated copy, Phase 9 becomes a mega-PR. **Mitigation:** decide early whether to enable i18n stubs during Phase 7 so strings ship translatable-ready from commit 1.
- **PDF rendering** (4b) — weasyprint has native lib deps (cairo, pango) that complicate Docker/deploy. **Mitigation:** choose reportlab if deploy simplicity matters more than HTML-template authoring.

---

## Phase count & rough effort

| Phase | Size | Cumulative |
|---|---|---|
| 4b Invoices | 6–8 commits | ~8 |
| 4c Notifications | 5–6 | ~14 |
| 5a Mail | 7–8 | ~22 |
| 5b Chat | 5–6 | ~28 |
| 6a Calendar | 5–6 | ~34 |
| 6b Kanban | 5 | ~39 |
| 6c Files | 5–6 | ~45 |
| 7a Landings | 4 | ~49 |
| 7b Pricing/Support | 3–4 | ~53 |
| 8 UX surfaces | 4 | ~57 |
| 9 i18n | 6–8 | ~65 |

**Total remaining to parity: ~55–65 commits across 11 phases.** For reference: the project is at 77 commits today post-Phase 4a, so full parity roughly **doubles** the commit count.

---

## Decisions (proposed defaults — revise if any feel wrong)

Rather than block on these, defaults below are taken; flip any of them and phases adjust.

1. **Phase ordering — dependency-driven as listed above.** No external business signal to front-load marketing or Calendar; the 4b → 4c → 5a → 5b critical path delivers the biggest chunk of "app-like" parity first.
2. **i18n posture — deferred entirely to Phase 9.** Translating-as-we-go adds overhead to every phase while strings are still churning. One focused sweep at the end is cheaper than eleven partial passes.
3. **PDF engine for Invoices — WeasyPrint.** HTML templates are far easier to maintain than programmatic drawing, and native deps (cairo/pango) are a solved problem via Docker base images or Homebrew on macOS dev machines. Rationale captured in Phase 4b spec.
4. **Real-time — HTMX polling only for v1.** 30s poll for Notifications, 3–5s for Chat active conversation. No Django Channels / ASGI until a real latency complaint justifies the infra complexity. Documented as Phase 10+ enhancement.
5. **Files — Mail/Chat attachments use their own FileField, NOT Phase 6c Files.** Phase 6c is a file-browser UI, not infrastructure. Keeping attachments independent lets 5a/5b ship before 6c and avoids coupling three phases.

**Net effect:** no change to the phase sequence above. Phase 4b can start its spec/plan cycle immediately.
