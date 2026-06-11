# Phase 6b — Kanban Implementation Plan

> Use superpowers:subagent-driven-development or executing-plans.

**Goal:** Single global Kanban board, 4 fixed status columns, full Card CRUD + SortableJS drag-and-drop between columns. New SortableJS dep (CDN). No new Python deps.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase6b-kanban-design.md`](../specs/2026-04-25-phase6b-kanban-design.md)

**6 commits:**

1. Card model + factory + tests
2. Views + URLs + tests (CRUD + move)
3. Board template + form + SortableJS integration
4. Sidebar + kanban icon
5. seed_demo cards
6. E2E tests

---

## Pre-flight

- [ ] Baseline: 333 unit + 41 E2E green on main
- [ ] Branch: phase6b-kanban (already)

---

## Task 1 — Card model

`apps/kanban/{__init__,apps,models}.py`. Register in INSTALLED_APPS.

**Tests:** is_overdue logic, priority_border_class, default ordering.

**Commit:** `feat(kanban): Card model with status + priority + position`

---

## Task 2 — Views + URLs + tests

6 routes per spec. CardMoveView is POST-only, validates status, shifts sibling positions.

**Tests:** access, board grouping, create with assignee, move shifts positions, invalid status rejected, delete removes.

**Commit:** `feat(kanban): board + CRUD + move views with position handling`

---

## Task 3 — Board template + SortableJS

```text
templates/kanban/
├── board.html        # 4-column grid + SortableJS
├── card_form.html    # create/edit
├── card_detail.html  # detail + delete
└── _card.html        # single card partial
```

**Commit:** `feat(kanban): 4-column board UI + SortableJS drag-and-drop`

---

## Task 4 — Sidebar + icon

Add `Kanban` NavItem. Register `trello` (or kanban-style) icon.

**Commit:** `feat(core): Kanban sidebar entry + icon`

---

## Task 5 — seed_demo

~20 cards distributed across columns with mixed assignees, priorities, due dates.

**Commit:** `feat(seed): demo kanban cards across columns`

---

## Task 6 — E2E

3 flows: board renders 4 columns, seeded cards in correct columns, create flow.

**Commit:** `test(e2e): kanban board + create flow`
