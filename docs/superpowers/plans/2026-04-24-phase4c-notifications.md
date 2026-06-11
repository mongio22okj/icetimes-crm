# Phase 4c — Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the cosmetic header bell with a real notification system. New `Notification` model, HTMX-polled header bell with unread badge, list page, mark-read flows, and emit points wired into Invoice + Order lifecycle events from Phases 4a + 4b.

**Architecture:** Single `Notification` table with a fixed `KIND_CHOICES` enum + denormalized `title`/`body`/`url`. Emit via direct calls from `apps/notifications/dispatch.py` (not signals). Bell polls `/notifications/bell/` via HTMX every 30s; context processor supplies initial unread count so first paint is accurate.

**Tech Stack:** Django 5.1 · HTMX (already vendored) · pytest · Playwright. No new dependencies.

**Reference spec:** [`docs/superpowers/specs/2026-04-24-phase4c-notifications-design.md`](../specs/2026-04-24-phase4c-notifications-design.md)

**6 commits:**

1. Notification model + dispatch module + factories + unit tests
2. Views + URLs + templates + view tests
3. Header bell wiring + context processor
4. Emit points in Invoice + Order
5. seed_demo additions
6. E2E tests

---

## Pre-flight

- [ ] **Baseline: 244 unit + 26 E2E tests green on `main`.**

Run: `uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `244 passed, 2 skipped`.

- [ ] **Create feature branch.**

Run: `git switch -c phase4c-notifications` (already done when executing this plan in-session).

---

## Task 1 — Notification model + dispatch + factory + tests

**Files:**

- Create: `apps/notifications/__init__.py`, `apps.py`
- Create: `apps/notifications/models.py`
- Create: `apps/notifications/dispatch.py`
- Create: `apps/notifications/migrations/__init__.py`, generated `0001_initial.py`
- Create: `apps/notifications/tests/__init__.py`, `factories.py`, `test_models.py`, `test_dispatch.py`
- Modify: `apex/settings/base.py` (register `apps.notifications`)

**Key code (see spec for full model):**
- `Notification` with `recipient`, `kind`, `title`, `body`, `url`, `read_at`, `created_at`
- `NotificationQuerySet.unread()` / `.read()`
- `dispatch.py`: `notify_invoice_sent/paid/void`, `notify_order_placed`, each iterating `User.objects.filter(is_staff=True, is_active=True)` and creating rows.

**Tests:**
- Model: unread/read queryset, mark_read, is_unread, ordering (~6)
- Dispatch: each emitter creates one row per staff user, skips non-staff/inactive, populates fields correctly (~6)

**Commit:** `feat(notifications): Notification model + dispatch helpers`

---

## Task 2 — Views + URLs + templates

**Files:**

- Create: `apps/notifications/views.py` (list, bell, mark_read, mark_all)
- Create: `apps/notifications/urls.py`
- Modify: `apex/urls.py` (include)
- Create: `templates/notifications/notification_list.html`, `_bell.html`, `_item.html`
- Create: `apps/notifications/tests/test_views.py`

**Behavior:**
- `NotificationListView` — paginated 20/page, user's own only
- `BellView` — returns `_bell.html` partial with `recent` (top 5) + `unread_count`
- `MarkReadView` — POST, PK-filtered to recipient=user, idempotent
- `MarkAllReadView` — POST, single UPDATE

**HTMX detection** without django-htmx: `request.headers.get("HX-Request") == "true"`.

**Tests:**
- Anonymous list → 302 login
- Logged-in list returns only own notifications
- Bell returns correct unread count + 5 recent
- Mark read sets read_at
- Mark read cross-user → 404
- Mark all → all user's unread become read

**Commit:** `feat(notifications): list/bell/mark-read views + templates`

---

## Task 3 — Header bell wiring + context processor

**Files:**

- Create: `apps/notifications/context_processors.py`
- Modify: `apex/settings/base.py` (register context processor)
- Modify: `templates/partials/header.html` (replace static bell)

**Context processor:**

```python
def notification_unread_count(request):
    if request.user.is_authenticated:
        return {"notification_unread_count": request.user.notifications.filter(read_at__isnull=True).count()}
    return {"notification_unread_count": 0}
```

**Header bell replacement** — Alpine `x-data="{open: false}"` dropdown, HTMX polls inner content every 30s, badge shows count (>99 → "99+"), dropdown shows recent 5 + "Mark all read" form + "View all" link.

**Commit:** `feat(notifications): HTMX-polled header bell + unread badge`

---

## Task 4 — Emit points in Invoice + Order

**Files:**

- Modify: `apps/invoices/models.py` (hook `mark_sent`, `mark_paid`, `mark_void`)
- Modify: `apps/orders/models.py` (hook `Order.save` on create)
- Modify: Invoice model tests if transition tests need to assert notifications aren't a side-effect that breaks isolation (use `Notification.objects.filter(...)` to verify count change)

**Lazy imports** inside method bodies to avoid circular-import risk.

**Verification:** run full unit suite — Invoice + Order transition tests should continue passing; new dispatch tests assert notifications are created.

**Commit:** `feat(notifications): emit on Invoice transitions + Order create`

---

## Task 5 — seed_demo additions

**Files:**

- Modify: `apps/core/management/commands/seed_demo.py`

Create ~10 notifications for the demo user (is_staff=True). Spread across all 4 kinds with mixed read states. Since Invoice/Order creation during seed now auto-emits notifications, we'll already have a bunch — just ensure the demo user is `is_staff=True` (already is) and let the existing seed paths populate. Add a few extra direct-creation notifications if count is too low for a good demo.

**Commit:** `feat(seed): notifications populated via dispatch + demo top-up`

---

## Task 6 — E2E tests

**Files:**

- Create: `tests/e2e/test_notifications.py`

**Scenarios (~3–4):**
- Header bell shows a non-zero unread badge on page load (seeded state)
- Click bell → dropdown visible with recent notifications
- "Mark all read" → badge disappears on next poll (or after refresh)
- Click notification list page → all rows visible, marked-read rows have different styling

**Commit:** `test(e2e): notification bell + list + mark-read flows`

---

## Done — Summary

- [ ] ~18 new unit tests + 3–4 new E2E tests passing
- [ ] Header bell shows live unread count (initial render + 30s poll refresh)
- [ ] Invoice.mark_sent/paid/void and Order creation emit notifications to all staff users
- [ ] `/notifications/` list page works with pagination, mark-read, mark-all-read
- [ ] seed_demo produces a demo user with ~10 notifications including unread ones
