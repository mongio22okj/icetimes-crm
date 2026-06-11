# Phase 7b — Pricing + Support

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Two public marketing surfaces under `apps/marketing/`. Pricing page with 3 tiers + monthly/annual toggle (Alpine, cosmetic) + FAQ accordion. Support page with cosmetic search box, help-articles grid, and a real contact form that stores submissions in a `SupportTicket` model.

## Context

Builds on [Phase 7a](2026-04-25-phase7a-landings-design.md) — same `apps/marketing/` app, same `marketing/base.html` chrome. Pricing has no DB needs. Support gets a small `SupportTicket` model so demo submissions persist (visible in admin).

## Goals

Ship pricing + support pages that round out the marketing surface — public, accessible from the marketing nav, and look at home next to the landing variants.

## Non-goals

- Stripe / payment integration
- Live chat widget
- Article search (cosmetic input only)
- Per-tier signup flows
- Email auto-response on ticket submission
- Admin reply UI for support tickets (admin list_display only)
- Internationalized pricing
- Per-region taxes / currencies

## Features

| Feature | Behaviour |
|---|---|
| **Pricing tiers** | 3 cards (Starter / Pro / Enterprise). Each lists ~6 included features. Middle tier highlighted as "Most popular". |
| **Monthly/Annual toggle** | Alpine `x-data` switch. Annual = 20% discount displayed. Cosmetic (no real billing). |
| **FAQ accordion** | 5 questions, Alpine-driven open/close. |
| **Support search box** | Cosmetic input — no backend wiring. |
| **Articles grid** | 6 cards with title + summary + cosmetic "Read article" link. |
| **Contact form** | Name + email + subject + body. POST creates SupportTicket, redirects with success flash. |
| **Sidebar** | Add "Pricing" and "Support" entries under existing "Marketing" group. |

## Architecture

### URLs

```text
apex/urls.py — already has /landing/ → apps.marketing.urls.

apps/marketing/urls.py adds:
  "pricing/"  → PricingView   (name="pricing")
  "support/"  → SupportView   (name="support")     # GET form, POST create ticket
```

### Data model — SupportTicket

```python
class SupportTicket(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.email}"
```

Migration `0001_initial.py` (first migration in `apps.marketing` since 7a was DB-less).

### Views

- `PricingView(TemplateView)` — pure template
- `SupportView(View)` — GET shows form, POST validates and saves; redirects with success flash

### Forms

```python
class SupportForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["name", "email", "subject", "body"]
        widgets = {...}
```

### Templates

```text
templates/marketing/
├── pricing.html
└── support.html
```

Both extend `marketing/base.html`.

## Testing

### Unit (~6 new tests)

- Pricing 200 anonymous + staff
- Support GET 200, form fields visible
- Support POST creates SupportTicket
- Support POST with invalid email returns 200 + form errors
- SupportTicket admin registered

### E2E (~2 new tests)

- Pricing page renders 3 tier cards
- Support form submission persists ticket

## Rollout — 3 commits (incl. docs)

1. docs (this + plan)
2. Pricing page + Support page + SupportTicket model + form + sidebar entries + tests
3. E2E
