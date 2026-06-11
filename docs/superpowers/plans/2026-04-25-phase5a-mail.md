# Phase 5a — Mail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Internal mail surface — staff users send/receive/reply/star/trash messages between each other. Three-pane layout, 5 folders (Inbox/Sent/Drafts/Starred/Trash), Django forms with HTMX-driven actions. Emits notifications via Phase 4c on new mail.

**Architecture:** Single `Message` model with self-FK `parent` for reply threading. Recipient-side state (`is_read`, `is_starred`, `is_trashed`) on the message itself; sender-side state deferred. Three-pane shell at `templates/mail/_layout.html` extending the existing dashboard layout.

**Tech Stack:** Django 5.1 · HTMX (already vendored) · pytest · Playwright. No new dependencies.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase5a-mail-design.md`](../specs/2026-04-25-phase5a-mail-design.md)

**7 commits:**

1. Message model + factories + unit tests
2. Forms + tests
3. Views + URLs + view tests
4. Three-pane templates + sidebar entry + mail icon
5. New-mail notification dispatch + `KIND_CHOICES` migration
6. seed_demo additions
7. E2E tests

---

## Pre-flight

- [ ] **Baseline: 266 unit + 30 E2E green on `main`.**
- [ ] **Branch:** already on `phase5a-mail` from `main`.

---

## Task 1 — Message model + factory + unit tests

Create `apps/mail/{__init__,apps,models}.py`, register in `INSTALLED_APPS`, generate migration.

**Model invariants** (per spec):
- `sent_at IS NULL` ⇔ draft (sender-only visibility)
- `is_read/starred/trashed` apply to recipient view only
- `parent` self-FK for replies; chain via `thread_chain()`

**Tests (~8):** queryset filters per folder, `folder_counts`, `thread_chain` for root + leaf + multi-level.

**Commit:** `feat(mail): Message model with reply threading + folder querysets`

---

## Task 2 — Forms + tests

`apps/mail/forms.py`:
- `ComposeForm` — `recipient` (User dropdown, staff only), `subject`, `body`. Tailwind classes via local BASE_INPUT.
- `ReplyForm` — `body` only (subject + recipient inferred from parent).

**Tests (~3):** field validation, empty subject rejected, reply minimal.

**Commit:** `feat(mail): ComposeForm + ReplyForm with staff-only recipient picker`

---

## Task 3 — Views + URLs + view tests

12 CBVs (per spec architecture section):

- `InboxView`, `SentView`, `DraftsView`, `StarredView`, `TrashView` — all extend a shared mixin chain + render the same folder template with different querysets
- `ThreadView` — opens message, marks read on first open
- `ComposeView` — GET form, POST send-or-save-draft
- `ReplyView` — POST creates child message
- `StarToggleView` / `TrashToggleView` — POST flip booleans
- `DraftEditView` — reuses ComposeView in edit mode (or separate CBV)
- `DraftDiscardView` — POST delete

**HTMX awareness:** Star/Trash views return refreshed row partial when `HX-Request: true`.

**Tests (~11):** access control + folder filtering + state transitions + reply chaining + cross-user 404s.

**Commit:** `feat(mail): folder/thread/compose/reply/action views + URLs`

---

## Task 4 — Three-pane templates + sidebar + icon

Templates:
- `templates/mail/_layout.html` — three-pane shell extending `layouts/dashboard.html`
- `templates/mail/_folder_links.html` — left pane folder nav with counts + Compose CTA
- `templates/mail/_message_row.html` — single message in middle pane
- `templates/mail/_thread.html` — right-pane thread + reply form
- Folder views: `inbox.html`, `sent.html`, `drafts.html`, `starred.html`, `trash.html` (all extend `_layout.html` with the same structure but folder-specific empty states)
- `templates/mail/compose.html` — right-pane = compose form
- `templates/mail/thread.html` — full page when accessed directly (right pane = thread)

Add `NavItem("Mail", "mail:inbox", ...)` to `apps/core/navigation.py`. Add `mail` icon SVG to `apps.core.templatetags.apex.ICONS`.

Update test_navigation.py expected labels.

**Commit:** `feat(mail): three-pane layout + folder views + sidebar entry`

---

## Task 5 — New-mail notification

Migration on `apps/notifications/`: add `"new_mail"` to `KIND_CHOICES`. New helper `notify_new_mail(message)` in `apps/notifications/dispatch.py`. Wire `ComposeView.post` (when sending, not draft) and `ReplyView.post` to fire.

**Test additions:** `test_dispatch.py` gets a test for `notify_new_mail`. `test_views.py` asserts notifications are created on send and not on draft.

**Commit:** `feat(notifications): new_mail kind + recipient-targeted dispatch`

---

## Task 6 — seed_demo

In `seed_demo`:
- Generate ~30 messages between demo and batch users
- Mix of states: ~70% sent, ~10% drafts (demo as sender), ~30% read, ~15% starred, ~10% trashed
- A few reply chains (parent → reply → reply)

**Verify:** after `seed_demo`, demo's inbox has unread messages, sent has outgoing items, drafts has 1-2 entries, starred has 2-3, trash has 1-2.

**Commit:** `feat(seed): mail factory + ~30 demo messages with reply chains`

---

## Task 7 — E2E tests

`tests/e2e/test_mail.py` — 4 Playwright flows:

1. Inbox click-through: open seeded mail → thread visible → marked read on next visit
2. Compose: fill to/subject/body, send → lands on Sent
3. Reply: open thread, click Reply, fill body, send → reply visible in thread
4. Star + Trash: star a message (persists), trash from inbox → appears in Trash

**Commit:** `test(e2e): mail inbox/compose/reply/star/trash flows`

---

## Done — Summary

- [ ] ~22 new unit + 4 new E2E tests passing
- [ ] Sidebar shows "Mail" under new "Apps" group
- [ ] Demo user's inbox has visible unread messages on first load
- [ ] Sending a message creates a `new_mail` notification visible in the bell
