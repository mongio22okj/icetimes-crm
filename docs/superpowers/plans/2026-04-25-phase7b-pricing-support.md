# Phase 7b — Pricing + Support Implementation Plan

**Goal:** Pricing tiers page + Support contact page, both public, both under `apps/marketing/`. SupportTicket model persists form submissions.

**Reference spec:** [`docs/superpowers/specs/2026-04-25-phase7b-pricing-support-design.md`](../specs/2026-04-25-phase7b-pricing-support-design.md)

**3 commits (incl. docs):**

1. docs
2. Pricing + Support views/templates/model/form/sidebar/tests
3. E2E

---

## Pre-flight

- [ ] Baseline: 375 unit + 50 E2E green on main
- [ ] Branch: phase7b-pricing-support (already)

---

## Task 1 — Pages + model + tests

- Add SupportTicket model + migration (first migration in apps/marketing)
- Add SupportForm
- Add PricingView + SupportView + URLs + sidebar entries (Pricing, Support under Marketing group)
- Templates: pricing.html (3 tiers + toggle + FAQ), support.html (search + articles grid + contact form)
- Update test_navigation expected labels
- ~6 unit tests covering both views

**Commit:** `feat(marketing): pricing page + support page with contact form`

---

## Task 2 — E2E

2 flows: pricing renders tiers; support form submission persists.

**Commit:** `test(e2e): pricing tiers + support form submission`
