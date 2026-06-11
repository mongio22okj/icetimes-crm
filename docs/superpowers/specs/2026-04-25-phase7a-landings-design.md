# Phase 7a — Marketing Landing Variants

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Four unauthenticated landing-page variants (Analytics, SaaS, CRM, eCommerce). Hero + features + testimonials + footer. Static content, hardcoded in templates. No models, no forms, no DB.

## Context

Per the roadmap [Phase 7a](../plans/2026-04-24-apex-parity-roadmap.md#phase-7a--landing-variants) — marketing surface; low-dependency, parallelizable. Single new app `apps/marketing/`, content hardcoded for now. Hero illustration uses inline SVG to avoid any image dependency.

Decisions:

- **Content source:** hardcoded in templates. No CMS / DB-backed editing.
- **Layout:** new `templates/marketing/base.html` — minimal chrome (logo + sign-in CTA in header, simple footer). Reuses Tailwind tokens but doesn't extend the dashboard.
- **Hero charts:** static SVG illustrations / placeholder graphics. ApexCharts demos are deferred; the dashboard itself already showcases them.
- **Sidebar:** add a single "Landings" entry under a new "Marketing" group, linking to a hub page that lists all 4 variants. Public marketing URLs don't require login.

## Goals

Ship four credible-looking landing pages distinguishable by hero copy + feature emphasis + color accents, each matching the dashboard's visual language, accessible without login, and discoverable from the dashboard via a sidebar hub.

## Non-goals

- Sign-up forms / lead capture on landings
- A/B testing
- Cookie banner / consent
- Multilingual (deferred to Phase 9 i18n)
- Pricing tiers (Phase 7b)
- Email signup
- Live chat widget
- Variant-specific blog or case-study sub-pages
- Mobile menu

## Features

| Variant | Headline emphasis | Accent | Feature focus |
|---|---|---|---|
| **Analytics** | "Decisions backed by data" | Blue | Dashboards, KPIs, drill-downs |
| **SaaS** | "Ship features, not infrastructure" | Indigo | Multi-tenant, billing, observability |
| **CRM** | "Every conversation, captured" | Emerald | Contacts, pipelines, follow-ups |
| **eCommerce** | "From cart to fulfillment" | Amber | Catalog, orders, inventory |

All four share the layout: top nav (logo + Sign in CTA), hero (headline + subhead + CTA + illustration), 3-feature grid, 3-testimonial section, footer.

## Architecture

### URLs

```text
apex/urls.py
  /landing/ → include("apps.marketing.urls")

apps/marketing/urls.py  (app_name = "marketing")
  ""                  → LandingsHubView      (name="hub")           # links to all 4
  "analytics/"        → AnalyticsView        (name="analytics")
  "saas/"             → SaasView             (name="saas")
  "crm/"              → CrmView              (name="crm")
  "ecommerce/"        → EcommerceView        (name="ecommerce")
```

### App layout

```text
apps/marketing/
├── __init__.py
├── apps.py            MarketingConfig
├── views.py           5 TemplateViews
├── urls.py
└── tests/
    ├── __init__.py
    └── test_views.py
```

### Views

All views are `TemplateView` subclasses with no auth gate (public access):

```python
class _MarketingView(TemplateView):
    pass  # no LoginRequiredMixin — public
```

### Templates

```text
templates/marketing/
├── base.html              # marketing chrome (nav + footer)
├── _hero.html             # reusable hero block parameterized by ctx
├── _features.html         # reusable 3-up feature grid
├── _testimonials.html     # reusable 3-up testimonial section
├── hub.html               # cards linking to all 4 variants
├── analytics.html
├── saas.html
├── crm.html
└── ecommerce.html
```

### Sidebar

```python
NavItem("Landings", "marketing:hub", "rocket",
        keywords=("marketing", "landing"),
        group="Marketing", requires_staff=True),
```

Add `rocket` icon SVG. New "Marketing" sidebar group sits between "Apps" and "Account".

### Public access

These views deliberately don't gate on auth. Adding `LoginRequiredMixin` would defeat their purpose (a marketing page that requires login). The sidebar entry is staff-gated, but anyone with the URL can view.

## Testing

### Unit (~6 new tests)

Each view:
- Returns 200 for anonymous user
- Returns 200 for authenticated user
- Renders headline keyword (e.g. "Analytics" appears on the analytics page)
- Hub links to all 4 variant URLs

### E2E (~2 new tests)

- Anonymous user can visit `/landing/analytics/` directly without login
- From the dashboard sidebar, "Landings" → hub → Click "Analytics" → analytics page renders

## Rollout — 3 commits

1. Marketing app + base layout + 4 variants + URLs + view tests + sidebar entry + rocket icon
2. (folded into 1) — single phase commit since no model/migration involved
3. E2E smoke tests

So **2 commits total** plus the docs commit.
