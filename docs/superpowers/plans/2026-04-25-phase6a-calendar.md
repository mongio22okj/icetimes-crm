# Phase 6a — Calendar Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Personal calendar with FullCalendar v6 (CDN). Month/week/day views, event CRUD via standard Django form pages (modal overlay via Alpine optional), JSON event-source endpoint, color-coded categories.

**Architecture:** New `apps/events/` (avoid stdlib `calendar` shadow). Single Event model, owner-scoped. URL prefix `/calendar/`. FullCalendar fetches `/calendar/events/?start=&end=` for the visible range.

**Tech Stack:** Django 5.1 · FullCalendar 6.1.15 (CDN). No new Python deps.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase6a-calendar-design.md`](../specs/2026-04-25-phase6a-calendar-design.md)

**6 commits:**

1. Event model + factory + tests
2. Views + URLs + JSON endpoint + tests
3. Calendar template + form + FullCalendar integration
4. Sidebar + calendar icon
5. seed_demo events
6. E2E tests

---

## Pre-flight

- [ ] Baseline: 319 unit + 38 E2E green on main
- [ ] Branch: phase6a-calendar (already)

---

## Task 1 — Event model

`apps/events/{__init__,apps,models}.py`. Register in INSTALLED_APPS.

**Tests:** to_fullcalendar shape, color property, Meta.indexes.

**Commit:** `feat(events): Event model with category colors + FullCalendar serializer`

---

## Task 2 — Views + URLs + JSON endpoint

5 routes. EventJsonView accepts `?start=<iso>&end=<iso>` and filters owner's events overlapping the range.

CRUD views are simple FBV/CBV, all owner-PK-filtered for safety.

**Commit:** `feat(events): CRUD views + JSON endpoint for FullCalendar`

---

## Task 3 — FullCalendar template

`templates/events/calendar.html` — vendor CSS+JS via CDN in `head_extra`/inline script. Bootstrap FullCalendar, hook events URL, redirect on `select` to create form.

`templates/events/event_form.html` — shared create/edit form with date inputs.

**Commit:** `feat(events): FullCalendar v6 integration + create/edit forms`

---

## Task 4 — Sidebar + icon

NavItem("Calendar", "events:calendar", ...). Add `calendar` icon. Update test_navigation.

**Commit:** `feat(core): Calendar sidebar entry + icon`

---

## Task 5 — seed_demo

Create ~12 events for demo across the next ~30 days, mixed categories (meetings/personal/deadlines), some all-day.

**Commit:** `feat(seed): demo calendar events across categories`

---

## Task 6 — E2E

3 flows: page renders FullCalendar grid, seeded events visible, create flow.

**Commit:** `test(e2e): calendar render + create flow`
