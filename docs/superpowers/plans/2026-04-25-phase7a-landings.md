# Phase 7a — Landings Implementation Plan

**Goal:** 4 unauthenticated landing variants (Analytics / SaaS / CRM / eCommerce). Static templates, no DB. Hub page + sidebar entry.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase7a-landings-design.md`](../specs/2026-04-25-phase7a-landings-design.md)

**3 commits (incl. docs):**

1. docs (this file + spec)
2. Marketing app + 4 variants + hub + sidebar entry + view tests
3. E2E smoke tests

---

## Pre-flight

- [ ] Baseline: 365 unit + 47 E2E green on main
- [ ] Branch: phase7a-landings (already)

---

## Task 1 — Marketing app + variants

`apps/marketing/{__init__,apps,views,urls}.py`. 5 TemplateViews (hub + 4 variants), all public (no auth).

Templates per spec.

Sidebar: NavItem under new "Marketing" group; rocket icon registered.

**Tests:** 200 for both anonymous and staff, headline text per variant, hub links to all 4. Update test_navigation expected labels + group order.

**Commit:** `feat(marketing): 4 landing variants + hub + sidebar entry`

---

## Task 2 — E2E

2 flows: anonymous visit to one variant; staff navigates from sidebar → hub → variant.

**Commit:** `test(e2e): landing variants accessible anonymously + via sidebar`
