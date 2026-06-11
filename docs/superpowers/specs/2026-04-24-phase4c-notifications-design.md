# Phase 4c — Notifications Module

**Date:** 2026-04-24
**Status:** Draft (pending approval)
**Scope:** Replace the cosmetic header bell with a real in-app notification system. New `apps/notifications/` app with a simple `Notification` model (recipient + kind + title + url + read_at), HTMX-polled header bell with unread-count badge, full list page, mark-read / mark-all-read flows, and emit points wired into the existing Invoice and Order state changes from Phases 4a + 4b.

## Context

Every previous phase has deferred the bell: [Phase 1 Shell](../plans/2026-04-22-phase1-shell-chrome.md) shipped the bell *icon* with a cosmetic red dot; the [README's Known Limitations](../../../README.md) lists notifications as unwired. Phase 4b just added Invoice state transitions that are the natural first consumers: `mark_sent`, `mark_paid`, `mark_void`. Phase 4c closes the loop.

Design tensions resolved:

- **Simple per-kind table vs. generic/polymorphic.** Chose simple: a fixed `KIND_CHOICES` enum + `url` CharField for the click-through target, stored denormalized `title` + `body`. A generic `ContentType` + `GenericForeignKey` approach adds introspection cost without a clear gain at the current scale (3–6 event kinds total). A single table makes indexes + queries trivial.
- **Direct calls vs. Django signals.** Chose direct calls from Invoice model methods (`notify_invoice_sent(self)` inside `mark_sent`). Signals obscure the call graph and make the emit points hard to discover; direct calls are explicit and easy to grep. Re-evaluate if emitters grow past ~10.
- **Polling vs. WebSockets.** HTMX polling every 30s for the bell, per the [roadmap's real-time decision](../plans/2026-04-24-apex-parity-roadmap.md#decisions-proposed-defaults--revise-if-any-feel-wrong). No Channels / ASGI.
- **Preferences.** No per-kind preferences tab in 4c. Defer to a future cycle if user demand materializes. In 4c, all staff receive all staff-targeted notifications; users don't receive any (only staff events fire).

## Goals

Ship a production-grade notification system that surfaces Invoice and Order lifecycle events on the existing header bell, with a dedicated list page for history and standard mark-read flows — without introducing new infra (no Redis, no Channels, no background workers).

## Non-goals

- Email delivery of notifications (console backend only if anything; not wired in 4c)
- Browser push / web-push API
- Per-user notification preferences (kind-level opt-in/out)
- Notification grouping, digests, or rate limiting
- Notifications to non-staff users
- Mobile push
- WebSocket / SSE real-time (polling only)
- Localization of notification text (deferred to Phase 9 i18n)
- Notification retention policy / auto-purge

## Features

| Feature | Behaviour |
|---|---|
| **Notification model** | `recipient` (User FK, CASCADE), `kind` (choice from a small enum), `title` (short text), `body` (optional longer text), `url` (click-through target), `read_at` (nullable timestamp), `created_at`. Index on `(recipient, read_at)` for unread-count + list queries. |
| **Header bell** | Replaces the static bell in `partials/header.html`. Badge shows unread count (capped display at "9+"). HTMX-polls `/notifications/bell/` every 30s. Click opens a dropdown showing 5 most recent notifications + "Mark all read" + "View all" link. |
| **List page** | `/notifications/` — paginated 20/page. Read vs unread visually distinguished (bold + colored left border on unread). Row-level "Mark read" button. |
| **Mark read flows** | `POST /notifications/<pk>/read/` toggles `read_at`. `POST /notifications/read-all/` marks every unread as read in one UPDATE. Both redirect back (or return HTMX partial for inline refresh). |
| **Emit points** | `Invoice.mark_sent`, `Invoice.mark_paid`, `Invoice.mark_void` each call `notify_invoice_*(self)`. New `Order` save with `created` flag emits `notify_order_placed(self)`. All emit helpers live in `apps/notifications/dispatch.py`. |
| **Seed demo** | Creates ~10 notifications for the demo user across all kinds and mixed read states, so the bell badge shows a non-zero count on first load. |

## Architecture

### URLs

```text
apex/urls.py
  /notifications/ → include("apps.notifications.urls")

apps/notifications/urls.py  (app_name = "notifications")
  ""                    → NotificationListView      (name="list")
  "<int:pk>/read/"      → MarkReadView              (name="mark_read")    # POST
  "read-all/"           → MarkAllReadView           (name="mark_all")     # POST
  "bell/"               → BellView                  (name="bell")         # GET (HTMX)
```

### New app layout

```text
apps/notifications/
├── __init__.py
├── apps.py              NotificationsConfig
├── models.py            Notification + NotificationQuerySet (+ unread manager)
├── dispatch.py          notify_invoice_sent / _paid / _void / notify_order_placed
├── views.py             4 CBVs
├── urls.py              4 routes
├── admin.py             Register Notification with list_display
├── context_processors.py  notification_unread_count (used by base layout)
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     NotificationFactory
    ├── test_models.py   unread queryset, mark-read, ordering
    ├── test_dispatch.py emit points create Notification rows
    ├── test_views.py    list/bell/mark routes + HTMX
```

### Views

```python
class NotificationListView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, ListView):
    paginate_by = 20
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    breadcrumb_title = "Notifications"

    def get_queryset(self):
        return self.request.user.notifications.order_by("-created_at")


class BellView(LoginRequiredMixin, View):
    """HTMX partial: badge count + recent 5 notifications for the dropdown."""

    def get(self, request):
        recent = request.user.notifications.order_by("-created_at")[:5]
        unread = request.user.notifications.unread().count()
        return render(request, "notifications/_bell.html",
                      {"recent": recent, "unread_count": unread})


class MarkReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not n.read_at:
            n.read_at = timezone.now()
            n.save(update_fields=["read_at"])
        if request.htmx:  # django-htmx — or check HX-Request header manually
            return render(request, "notifications/_bell.html", ...)
        return redirect(n.url or "notifications:list")


class MarkAllReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        request.user.notifications.unread().update(read_at=timezone.now())
        return redirect("notifications:list")
```

> **`request.htmx`** is a convenience provided by `django-htmx`. The existing codebase doesn't use it — we'll check the raw `HX-Request` header instead to avoid a new dep: `request.headers.get("HX-Request") == "true"`.

### Templates

```text
templates/notifications/
├── notification_list.html    # full page
├── _bell.html                # HTMX partial for header bell (button + badge + dropdown content)
└── _item.html                # single notification row (used by list + bell)
```

The bell dropdown reuses Alpine.js `x-data="{open: false}"` pattern from `nav_user_menu.html`. HTMX polls the *inner content* of the dropdown, not the button itself, so Alpine's open state survives swaps.

### Context processor

`apps.notifications.context_processors.notification_unread_count` exposes `notification_unread_count` to every authenticated request. Used by the initial render of the bell (so the first page load shows the right badge without waiting 30s for the first HTMX poll).

Registered in `apex/settings/base.py`'s `TEMPLATES.OPTIONS.context_processors`.

### Dispatch module

```python
# apps/notifications/dispatch.py
from django.contrib.auth import get_user_model
from apps.notifications.models import Notification

User = get_user_model()


def _staff_recipients():
    return User.objects.filter(is_staff=True, is_active=True)


def notify_invoice_sent(invoice):
    for user in _staff_recipients():
        Notification.objects.create(
            recipient=user,
            kind="invoice_sent",
            title=f"Invoice {invoice.number} sent",
            body=f"to {invoice.customer.name}",
            url=invoice.get_absolute_url(),
        )


def notify_invoice_paid(invoice):
    for user in _staff_recipients():
        Notification.objects.create(
            recipient=user,
            kind="invoice_paid",
            title=f"Invoice {invoice.number} marked paid",
            body=f"${invoice.total} from {invoice.customer.name}",
            url=invoice.get_absolute_url(),
        )


def notify_invoice_void(invoice):
    for user in _staff_recipients():
        Notification.objects.create(
            recipient=user,
            kind="invoice_void",
            title=f"Invoice {invoice.number} voided",
            url=invoice.get_absolute_url(),
        )


def notify_order_placed(order):
    for user in _staff_recipients():
        Notification.objects.create(
            recipient=user,
            kind="order_placed",
            title=f"New order {order.number}",
            body=f"from {order.customer.name}",
            url=order.get_absolute_url() if hasattr(order, "get_absolute_url") else f"/orders/{order.pk}/",
        )
```

### Invoice + Order integration

In `apps/invoices/models.py`:

```python
def mark_sent(self) -> None:
    self._transition("sent", "sent_at")
    from apps.notifications.dispatch import notify_invoice_sent
    notify_invoice_sent(self)

def mark_paid(self) -> None:
    self._transition("paid", "paid_at")
    from apps.notifications.dispatch import notify_invoice_paid
    notify_invoice_paid(self)

def mark_void(self) -> None:
    self._transition("void", "voided_at")
    from apps.notifications.dispatch import notify_invoice_void
    notify_invoice_void(self)
```

Imports are lazy (inside the method) to avoid a circular-import risk if `apps.notifications` ever needs to import from `apps.invoices` later.

In `apps/orders/models.py::Order.save`:

```python
def save(self, *args, **kwargs):
    is_create = self.pk is None
    super().save(*args, **kwargs)
    if not self.number:
        self.number = f"ORD-{self.pk:05d}"
        Order.objects.filter(pk=self.pk).update(number=self.number)
    if is_create:
        from apps.notifications.dispatch import notify_order_placed
        notify_order_placed(self)
```

## Data model

```python
# apps/notifications/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True)

    def read(self):
        return self.filter(read_at__isnull=False)


class Notification(models.Model):
    KIND_CHOICES = [
        ("invoice_sent", "Invoice sent"),
        ("invoice_paid", "Invoice paid"),
        ("invoice_void", "Invoice voided"),
        ("order_placed", "Order placed"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    url = models.CharField(max_length=500, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
            models.Index(fields=["recipient", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.title}"

    def mark_read(self) -> None:
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    @property
    def is_unread(self) -> bool:
        return self.read_at is None
```

## Testing

### Unit (~18 new tests)

**`test_models.py` (~6):**
- Unread queryset filters read rows
- Read queryset filters unread rows
- `mark_read()` sets `read_at`
- Calling `mark_read()` twice keeps the first timestamp
- Default ordering is newest first
- `is_unread` property

**`test_dispatch.py` (~6):**
- `notify_invoice_sent` creates one row per staff user
- Non-staff users receive nothing
- Inactive users receive nothing
- Title/body/url fields populated correctly
- `notify_order_placed` fires on Order creation (integration with save() override)
- Invoice `mark_sent` fires notification (integration)

**`test_views.py` (~6):**
- List redirects anonymous to login
- List returns user's own notifications only
- Bell partial returns unread count + recent 5
- `MarkReadView` POST sets `read_at`
- `MarkReadView` cross-user returns 404 (PK-filter on recipient)
- `MarkAllReadView` POST marks all user's unread as read

### E2E (~3 new tests)

- Header bell shows unread badge on page load (count > 0 after seed_demo)
- Click bell → dropdown shows recent notifications
- Click "Mark all read" → badge disappears, dropdown marks notifications read
- Click single notification → navigates to its `url` target

## Rollout — 6 commits

1. **Notification model + dispatch module + factory + model/dispatch tests** — pure data layer, no views.
2. **Views + URLs + templates (list, bell partial, item partial)** — staff-gated list, HTMX bell endpoint, mark-read flows.
3. **Header bell wiring + context processor** — replace the static bell in `templates/partials/header.html` with the dynamic one; register context processor for initial-render badge.
4. **Emit points** — wire `Invoice.mark_*` and `Order.save` to call dispatch helpers. Adjust existing Invoice tests if any mock the transition methods.
5. **seed_demo additions** — create ~10 notifications for the demo user with mixed read states. Verify bell badge shows a non-zero count after fresh seed.
6. **E2E tests** — 3–4 Playwright flows covering the bell UI and mark-read behavior.

## Open questions

1. **Order emit timing.** Should the order emit fire only on initial create, or also on `status` transitions (pending → paid → shipped)? *Proposed:* create only for v1; status transitions deferred to avoid notification spam.
2. **"View all" link in dropdown.** Show even when empty? *Proposed:* Hide the link when no notifications exist; keep the dropdown minimal.
3. **Read-state visual treatment.** Which of unread-only-bold, colored-dot, left-border-accent? *Proposed:* bold title + primary-colored left border (4px) on unread rows.

## Forward-compatibility notes (for 5a Mail and 5b Chat)

- **Mail (5a):** New mail arrival emits `notify_new_mail(message)` into the same `Notification` table. Add `"new_mail"` to `KIND_CHOICES` in a migration.
- **Chat (5b):** New message ping ditto — `notify_new_chat(message)`. The existing bell UI scales to both.
- **Preferences tab (future):** Would add `UserNotificationPreference(user, kind, enabled)` and have `dispatch.py` consult it before creating rows. The 4c scheme accommodates this without schema change to `Notification` itself.
