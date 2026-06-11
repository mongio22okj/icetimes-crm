# Phase 8 — UX Surfaces Implementation Plan

**Goal:** Three smaller surfaces in one phase: Wizard (multi-step form), Charts showcase, Lock-screen.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase8-ux-surfaces-design.md`](../specs/2026-04-25-phase8-ux-surfaces-design.md)

**4 commits (incl. docs):**

1. docs
2. Wizard
3. Charts showcase
4. Lock-screen + E2E for all three

---

## Pre-flight

- [ ] Baseline: 380 unit + 52 E2E green on main
- [ ] Branch: phase8-ux-surfaces (already)

---

## Task 1 — Wizard

`apps/wizard/{__init__,apps,models,forms,views,urls}.py`. WizardSubmission model + migration. 4 step views using session for inter-step state.

Templates: `templates/wizard/{step1,step2,step3,review,done}.html` extending dashboard layout. Progress bar partial.

**Sidebar:** Add "Onboarding" entry under a new "Showcase" group (will host wizard + charts).

**Tests:** session flow, persistence, skip-ahead redirects.

**Commit:** `feat(wizard): 4-step onboarding with session-backed state`

---

## Task 2 — Charts showcase

Single view + template + URL. Renders 8 ApexCharts variants on one page using existing `static/js/charts.js` patterns + new factories for showcase variants.

**Sidebar:** Add "Charts" entry under Showcase group.

**Tests:** 200 for staff.

**Commit:** `feat(dashboard): charts showcase with 8 ApexCharts variants`

---

## Task 3 — Lock-screen + E2E

`LockScreenView` in `apps/accounts/views.py`. Middleware in `apps/accounts/middleware.py`. Nav user-menu button.

E2E flows for wizard happy path, charts page, lock+unlock.

**Commit:** `feat(accounts): session lock-screen + middleware + nav button` + `test(e2e): wizard + charts + lock flows`

(May split into 2 commits if cleaner.)
