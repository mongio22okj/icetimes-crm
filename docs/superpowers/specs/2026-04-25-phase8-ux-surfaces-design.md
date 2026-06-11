# Phase 8 — UX Surfaces

**Date:** 2026-04-25
**Status:** Draft
**Scope:** Three smaller UX-pattern surfaces bundled into one phase: a multi-step Wizard, a Charts showcase gallery, and a Lock-screen that requires re-authentication.

## Context

Per roadmap [Phase 8](../plans/2026-04-24-apex-parity-roadmap.md#phase-8--ux-pattern-surfaces) — none of these justify a phase on their own; bundled because each is small (~1 commit) and shares the goal of exercising a parity-only UX pattern.

## Goals

Ship three demo surfaces that round out the parity coverage with the Apex Next.js reference.

## Non-goals

- Wizard with branching paths or conditional fields
- Wizard step persistence across sessions
- Live data in the charts showcase (uses static demo numbers)
- Real session-locking middleware on inactivity
- Auto-lock after N minutes
- Email-based unlock recovery

## Features

### Wizard

| Aspect | Behaviour |
|---|---|
| **App** | New `apps/wizard/` |
| **Steps** | 4 steps: Account → Company → Preferences → Review |
| **Storage between steps** | Django session (`request.session["wizard"]`) |
| **Progress UI** | Numbered indicator at top, current step highlighted |
| **Final submit** | Persists a `WizardSubmission` row (admin-registered for review) and clears session state |
| **Restart** | Button on review step to reset and start over |

### Charts showcase

| Aspect | Behaviour |
|---|---|
| **App** | Lives in `apps/dashboard/` (extends existing chart code) |
| **URL** | `/charts/` |
| **Content** | Single page rendering 8 ApexCharts variants in a grid: bar, line, area, donut, radial, heatmap, scatter, mixed |
| **Data** | Hardcoded sample series in a small JS object |
| **Theme** | Charts respect dark/light via existing chart factories |

### Lock-screen

| Aspect | Behaviour |
|---|---|
| **App** | Lives in `apps/accounts/` next to existing auth views |
| **Trigger** | "Lock" button in nav user dropdown |
| **URL** | `/lock/` — sets `request.session["locked"] = True`, then renders lock template |
| **Unlock** | Password input — re-authenticates current user; on success removes session flag |
| **Middleware (optional)** | Lightweight middleware redirects all dashboard routes to `/lock/` while session is locked. Logout/login pages stay accessible. |

## Architecture

### URLs

```text
apex/urls.py adds:
  /wizard/    → apps.wizard.urls
  /charts/    → ChartsShowcaseView (in apps.dashboard.urls)
  /lock/      → LockScreenView (in apex/urls.py top-level)
```

### App layout — wizard

```text
apps/wizard/
├── apps.py
├── models.py            WizardSubmission
├── forms.py             AccountStepForm + CompanyStepForm + PreferencesStepForm
├── views.py             4 step views + FinalView
├── urls.py
└── tests/test_*.py
```

### Data model

```python
class WizardSubmission(models.Model):
    user = FK(User, null=True, blank=True)
    name = CharField()
    email = EmailField()
    company = CharField(blank=True)
    role = CharField(blank=True)
    team_size = CharField(blank=True)  # choices: 1, 2-10, 11-50, 50+
    theme = CharField(default="system")  # light/dark/system
    notifications_enabled = BooleanField(default=True)
    submitted_at = DateTimeField(auto_now_add=True)
```

### Lock screen

```python
class LockScreenView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")
        request.session["locked"] = True
        return render(request, "accounts/lock.html")

    def post(self, request):
        # User submits password
        from django.contrib.auth import authenticate
        password = request.POST.get("password", "")
        if authenticate(username=request.user.username, password=password):
            request.session.pop("locked", None)
            return redirect("dashboard")
        return render(request, "accounts/lock.html", {"error": "Incorrect password."})
```

Middleware:

```python
class LockedSessionMiddleware:
    """If session is locked, redirect dashboard routes to /lock/."""
    EXEMPT_PREFIXES = ("/accounts/login/", "/accounts/logout/", "/lock/", "/static/", "/landing/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.session.get("locked")
            and not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES)
        ):
            return redirect("lock")
        return self.get_response(request)
```

## Testing

### Unit (~10 new tests)

**Wizard:**
- Step 1 GET shows account form
- Step 1 POST stores in session and redirects to step 2
- Step 4 (review) shows accumulated session data
- Final submit persists WizardSubmission and clears session
- Skipping ahead without earlier steps redirects to step 1

**Charts showcase:**
- Page returns 200 for staff, redirects anonymous

**Lock screen:**
- GET sets session["locked"]
- Wrong password keeps session locked
- Correct password unlocks + redirects
- Middleware redirects dashboard to /lock/ when locked
- Middleware exempts login/logout/static

### E2E (~3 new tests)

- Wizard happy path: fill 3 steps, see review, submit
- Charts page renders 8 chart canvases
- Lock → enter password → unlock returns to dashboard

## Rollout — 4 commits (incl. docs)

1. docs
2. Wizard (model + 4 step views + templates + tests + sidebar)
3. Charts showcase (single view + template + nav entry)
4. Lock-screen (view + middleware + template + nav user-menu button + tests + E2E for all three)
