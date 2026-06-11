# Phase 4b — Invoices Module

**Date:** 2026-04-24
**Status:** Draft (pending approval)
**Scope:** Second of three sub-phases closing the "missing CRUD modules" gap in the parity roadmap. Introduces a dedicated `Invoice` + `InvoiceItem` model pair, staff-gated CRUD, line-item inline formset, status state machine, WeasyPrint-rendered PDF export, and a token-authenticated public view for sharing with customers.

## Context

[Phase 4a](../plans/2026-04-23-phase4a-customers.md) shipped the `Customer` model and migrated `Order.customer` to point at it. Phase 4b layers Invoices on top: each invoice belongs to a Customer and carries line items priced independently of Products (invoices can bill for services, adjustments, or one-off items not in the catalog).

Design tensions resolved here:

- **Invoice vs. Order.** Orders track fulfillment (shipping, status: pending → shipped → delivered). Invoices track billing (status: draft → sent → paid). They're separate models, with an optional `Invoice.order` FK for the "generate invoice from order" flow. Copying items at generation time (not live-linking) keeps invoices immutable once sent.
- **PDF engine.** WeasyPrint chosen over ReportLab. HTML templates are cheaper to iterate visually and match the Tailwind design tokens already in use. Native deps (cairo, pango, gdk-pixbuf) are a one-time dev-machine setup and a single apt-get line in Docker.
- **Public sharing.** Each invoice gets a UUID `public_token` field at creation. Public URL `/invoices/public/<uuid>/` lets customers view + download the PDF without authentication, matching the reference Apex behavior. Tokens are effectively unguessable; rotation deferred to a future phase.

## Goals

Ship a staff-gated Invoices module with draft/sent/paid/void lifecycle, PDF export, and a public read-only view; wire one optional bridge (generate invoice from an existing Order) to demonstrate the integration pattern without coupling the two models.

## Non-goals

- Partial / split payments (paid = fully paid)
- Multi-currency (USD hardcoded; locale/currency picker is Phase 9 work)
- Per-line-item or per-jurisdiction tax rules (single `tax_rate` on the whole invoice)
- Actual email sending when status → sent (that's Phase 4c Notifications territory; 4b only records the status change)
- Automatic overdue transitions via cron (overdue is *derived* from `due_date < today and status = "sent"`, not stored)
- Recurring invoices / subscription billing
- Customer self-portal login (public view is token-based only)
- Payment gateway integration (Stripe / PayPal) — out of scope for parity
- Credit notes / refund documents

## Features

| Feature | Behaviour |
|---|---|
| **Invoice CRUD** | Staff-gated list / detail / create / edit / delete. List paginated 20/page with number + customer + issue_date + due_date + total + status pill + row-actions. Detail shows header card + line items table + totals block + action bar (status-dependent). Edit allowed only while `status = "draft"`. Delete allowed only while `status = "draft"`. |
| **Line items** | Django inline formset on the create/edit form. HTMX-driven "Add row" / "Remove row" without page reload. Each row: description, quantity (positive int), unit_price (decimal). Row amount computed client-side for preview, recomputed server-side on save. Minimum 1 item enforced at form-level. |
| **Status state machine** | `DRAFT → SENT → (PAID \| VOID)`. Transitions are POST-only endpoints gated by allowed-from check on the model. `OVERDUE` is derived, never stored. Illegal transitions return 400. |
| **Auto-numbering** | `INV-YYYY-NNNN` format, sequence reset each year. Assigned on first save (even drafts get a number). Uniqueness enforced by DB constraint. |
| **PDF export** | WeasyPrint renders `invoice_pdf.html` to a PDF served as `Content-Disposition: attachment`. Staff path: `/invoices/<pk>/pdf/`. Public path: `/invoices/public/<token>/pdf/`. |
| **Public view** | UUID-token read-only page at `/invoices/public/<token>/` showing invoice details + PDF download link. No auth required. Safe to share via email. |
| **Order bridge** | Button on Order detail → creates a draft Invoice pre-populated with the order's Customer and OrderItems copied into InvoiceItems. Preserves `Invoice.order` FK for audit. Optional — staff can still create free-form invoices. |
| **Sidebar nav** | New "Invoices" entry under Commerce group (between Orders and Customers). Staff-only via `requires_staff=True`. |
| **Seed update** | `seed_demo` creates ~15 Invoices across mixed statuses (5 draft, 5 sent, 3 paid, 2 void), with 1–4 line items each, tied to existing Customers. |

## Architecture

### URLs

```text
apex/urls.py
  /invoices/ → include("apps.invoices.urls")

apps/invoices/urls.py  (app_name = "invoices")
  ""                               → InvoiceListView          (name="list")
  "new/"                           → InvoiceCreateView        (name="create")
  "<int:pk>/"                      → InvoiceDetailView        (name="detail")
  "<int:pk>/edit/"                 → InvoiceUpdateView        (name="edit")
  "<int:pk>/delete/"               → InvoiceDeleteView        (name="delete")    # POST-only
  "<int:pk>/send/"                 → InvoiceSendView          (name="send")      # POST-only
  "<int:pk>/pay/"                  → InvoicePayView           (name="pay")       # POST-only
  "<int:pk>/void/"                 → InvoiceVoidView          (name="void")      # POST-only
  "<int:pk>/pdf/"                  → InvoicePdfView           (name="pdf")
  "<int:pk>/items/add-row/"        → InvoiceItemAddRowView    (name="add_row")   # HTMX
  "public/<uuid:token>/"           → PublicInvoiceView        (name="public")
  "public/<uuid:token>/pdf/"       → PublicInvoicePdfView     (name="public_pdf")

apps/orders/urls.py  (addition)
  "<int:pk>/generate-invoice/"     → GenerateInvoiceFromOrderView  (name="generate_invoice")  # POST-only
```

### New app layout

```text
apps/invoices/
├── __init__.py
├── apps.py              InvoicesConfig (default_auto_field = BigAutoField)
├── models.py            Invoice + InvoiceItem + InvoiceQuerySet
├── forms.py             InvoiceForm + InvoiceItemFormSet
├── views.py             11 CBVs (8 staff, 2 public, 1 HTMX row adder)
├── urls.py              12 routes
├── admin.py             register Invoice + InvoiceItem inline
├── pdf.py               render_invoice_pdf() helper wrapping WeasyPrint
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     InvoiceFactory + InvoiceItemFactory
    ├── test_models.py   state machine, numbering, totals, derived overdue
    ├── test_forms.py    formset validation, tax math
    ├── test_views.py    CRUD + transitions + public + PDF + access control
    └── test_pdf.py      smoke-test WeasyPrint renders a non-empty PDF
```

### Views

All staff CBVs use the existing mixin stack:

```python
class InvoiceListView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Invoice
    paginate_by = 20
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    breadcrumb_title = "Invoices"

    def get_queryset(self):
        return (Invoice.objects
                .select_related("customer")
                .annotate(items_count=models.Count("items", distinct=True))
                .order_by("-issue_date", "-number"))
```

Public views (`PublicInvoiceView`, `PublicInvoicePdfView`) **do not** include `LoginRequiredMixin` — they authenticate via the UUID token parameter:

```python
class PublicInvoiceView(DetailView):
    model = Invoice
    slug_field = "public_token"
    slug_url_kwarg = "token"
    template_name = "invoices/invoice_public.html"

    def get_queryset(self):
        return Invoice.objects.exclude(status="draft").select_related("customer")
```

Drafts are 404-ed on the public route so staff can't accidentally leak in-progress work.

Transition views are thin:

```python
class InvoiceSendView(LoginRequiredMixin, StaffRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        try:
            invoice.mark_sent()
        except InvalidTransition as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"Invoice {invoice.number} marked as sent.")
        return redirect(invoice.get_absolute_url())
```

`mark_paid` and `mark_void` follow the same pattern. `InvoiceDeleteView` checks `status == "draft"` before deleting.

### Templates

```text
templates/invoices/
├── invoice_list.html              table + status-filter pills + pagination
├── invoice_detail.html            header card + items table + totals + action bar
├── invoice_form.html              header fields + inline formset + HTMX row UI
├── invoice_pdf.html               WeasyPrint-targeted layout (print CSS, no interactive elements)
├── invoice_public.html            customer-facing view (no nav chrome; standalone layout)
├── _invoice_status_pill.html      draft / sent / paid / void / overdue pills
├── _invoice_item_row.html         single <tr> formset row (reused by HTMX add-row)
└── _invoice_totals.html           subtotal + tax + total block (reused by form and detail)
```

A new `templates/layouts/public.html` is added for the public invoice view — dashboard chrome is inappropriate for a customer-facing page. It's a minimal layout: logo + content + footer, inheriting `base.html` for design tokens.

### Sidebar

In `apps/core/navigation.py`, add between Customers and Orders:

```python
NavItem("Invoices", "invoices:list", "file-text",
        keywords=("billing", "finance"), group="Commerce",
        requires_staff=True),
```

Add `file-text` icon to `apps/core/templatetags/apex.py::ICONS`.

### Dependencies

**New Python deps (pyproject.toml):**

```toml
dependencies = [
  # ... existing ...
  "weasyprint>=62.0",
]
```

**System deps (dev machines + deploy target):**

- macOS: `brew install cairo pango gdk-pixbuf libffi` (WeasyPrint docs)
- Debian/Docker: `apt-get install libpango-1.0-0 libpangoft2-1.0-0`

Document in README's Requirements section. Not auto-installed by `uv sync` (system libs sit outside Python's reach).

No new JS deps. HTMX already vendored; inline formset add-row uses HTMX GET + server-rendered partial.

## Data model

### Invoice model

```python
# apps/invoices/models.py
import uuid
from datetime import date
from decimal import Decimal
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer


class InvalidTransition(Exception):
    pass


class InvoiceQuerySet(models.QuerySet):
    def overdue(self):
        return self.filter(status="sent", due_date__lt=timezone.now().date())


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]

    number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="invoices",
    )
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ["-issue_date", "-number"]
        indexes = [models.Index(fields=["status", "due_date"])]

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse("invoices:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    def _generate_number(self) -> str:
        year = self.issue_date.year if self.issue_date else timezone.now().year
        prefix = f"INV-{year}-"
        with transaction.atomic():
            last = (Invoice.objects
                    .select_for_update()
                    .filter(number__startswith=prefix)
                    .order_by("-number")
                    .first())
            if last:
                seq = int(last.number.split("-")[-1]) + 1
            else:
                seq = 1
            return f"{prefix}{seq:04d}"

    # --- totals ---
    @property
    def subtotal(self) -> Decimal:
        return sum((item.amount for item in self.items.all()), Decimal("0"))

    @property
    def tax_amount(self) -> Decimal:
        return (self.subtotal * self.tax_rate / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def total(self) -> Decimal:
        return self.subtotal + self.tax_amount

    # --- derived status ---
    @property
    def is_overdue(self) -> bool:
        return self.status == "sent" and self.due_date < timezone.now().date()

    @property
    def display_status(self) -> str:
        return "overdue" if self.is_overdue else self.status

    # --- state machine ---
    _ALLOWED = {
        "draft": {"sent"},
        "sent": {"paid", "void"},
        "paid": set(),
        "void": set(),
    }

    def _transition(self, to: str, timestamp_field: str):
        if to not in self._ALLOWED[self.status]:
            raise InvalidTransition(
                f"Cannot transition {self.number} from {self.status} to {to}."
            )
        self.status = to
        setattr(self, timestamp_field, timezone.now())
        self.save(update_fields=["status", timestamp_field, "updated_at"])

    def mark_sent(self):
        self._transition("sent", "sent_at")

    def mark_paid(self):
        self._transition("paid", "paid_at")

    def mark_void(self):
        self._transition("void", "voided_at")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return f"{self.description} × {self.quantity}"

    @property
    def amount(self) -> Decimal:
        return (Decimal(self.quantity) * self.unit_price).quantize(Decimal("0.01"))
```

Key design notes:

- `number` generated with `select_for_update` + prefix-filtered `order_by("-number").first()` — safe under concurrent inserts within the same year. First-save-wins.
- `order` FK is `SET_NULL` so deleting an Order doesn't cascade-delete the Invoice (billing record must outlive fulfillment record).
- `customer` is `PROTECT` (same reasoning as Orders). Archived Customers still resolve via Phase 4a's `base_manager_name = "all_objects"`.
- State machine is a dict lookup + exception — no `django-fsm` dependency. The 4 legal transitions are small enough to reason about by eye.
- `public_token` is `editable=False` so it never surfaces on a form. Rotation is explicit: `invoice.public_token = uuid.uuid4(); invoice.save()` (left to a future phase if needed).
- Totals are properties, not DB columns. Computed on-the-fly from `items`. Cheap for detail pages; list pages use an annotation or accept the cost.

### Forms & formset

```python
# apps/invoices/forms.py
from django import forms
from django.forms import inlineformset_factory
from apps.core.forms import BASE_INPUT  # Tailwind classes
from .models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "order", "issue_date", "due_date", "tax_rate", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "due_date":   forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "notes":      forms.Textarea(attrs={"rows": 3, "class": BASE_INPUT}),
        }

    def clean(self):
        cleaned = super().clean()
        issue = cleaned.get("issue_date")
        due = cleaned.get("due_date")
        if issue and due and due < issue:
            raise forms.ValidationError("Due date cannot be before issue date.")
        return cleaned


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    fields=["description", "quantity", "unit_price"],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
    widgets={
        "description": forms.TextInput(attrs={"class": BASE_INPUT}),
        "quantity":    forms.NumberInput(attrs={"class": BASE_INPUT, "min": 1}),
        "unit_price":  forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01"}),
    },
)
```

`validate_min=True` enforces the "at least one line item" rule at the formset level.

HTMX row addition:

```html
<!-- invoice_form.html snippet -->
<tbody id="invoice-items"
       hx-target="closest tbody"
       hx-swap="beforeend">
  {{ formset.management_form }}
  {% for form in formset %}
    {% include "invoices/_invoice_item_row.html" %}
  {% endfor %}
</tbody>
<button hx-get="{% url 'invoices:add_row' %}?index={{ formset.total_form_count }}"
        type="button" class="...">Add row</button>
```

`InvoiceItemAddRowView` returns a freshly-rendered blank row partial with incremented form index, and bumps `TOTAL_FORMS` via HX-Trigger → Alpine updates the hidden field. Row remove = Alpine sets `DELETE` input + hides the row.

### PDF rendering

```python
# apps/invoices/pdf.py
from django.template.loader import render_to_string
from weasyprint import HTML


def render_invoice_pdf(invoice, *, request=None) -> bytes:
    html_str = render_to_string("invoices/invoice_pdf.html",
                                {"invoice": invoice}, request=request)
    base_url = request.build_absolute_uri("/") if request else None
    return HTML(string=html_str, base_url=base_url).write_pdf()
```

`base_url` lets WeasyPrint resolve `{% static %}` references (logo, webfonts) correctly.

`InvoicePdfView` / `PublicInvoicePdfView`:

```python
def get(self, request, *args, **kwargs):
    invoice = self.get_object()
    pdf = render_invoice_pdf(invoice, request=request)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{invoice.number}.pdf"'
    return response
```

### Seed_demo update

```python
# apps/core/management/commands/seed_demo.py
from apps.invoices.tests.factories import InvoiceFactory

# ... after Customers/Orders are created:
for customer in Customer.objects.all()[:12]:
    InvoiceFactory.create_batch(random.randint(1, 3), customer=customer)
# Distribute statuses across the batch post-hoc
```

Factories produce a realistic spread of statuses and line items.

## Error handling

- **Illegal status transition:** `InvalidTransition` caught in the view, surfaces as a `messages.error` flash, redirects back to detail. No 500.
- **Edit after send:** `InvoiceUpdateView` dispatches a 403 if `status != "draft"` (method override).
- **Delete after send:** same pattern — 403 if `status != "draft"`.
- **Public view on a draft:** 404 (queryset excludes drafts).
- **PDF render failure:** log the WeasyPrint exception, surface 500 error page (no silent fallback — PDF failures are actionable).
- **Formset with zero line items:** `validate_min=True` returns the form with a non-field error "Invoice must have at least one line item."
- **Due-date-before-issue-date:** caught in `InvoiceForm.clean`.
- **Concurrent number generation:** `select_for_update` inside `transaction.atomic` serializes number assignment within the same year. Worst case two simultaneous inserts → one waits.
- **Archived customer on invoice:** allowed. Invoice keeps working via `base_manager_name = "all_objects"`. Public view renders archived-customer name fine.

## Testing

### Unit (pytest) — ~22 new tests

**`test_invoice_models.py`** (~10):

- Number generation: first invoice of 2026 → `INV-2026-0001`
- Number generation: second invoice of 2026 → `INV-2026-0002`
- Number generation: different year starts fresh at `-0001`
- `subtotal` sums item amounts with 2-decimal precision
- `tax_amount` = subtotal × tax_rate / 100, rounded
- `total` = subtotal + tax_amount
- `is_overdue` true when sent + due_date in past, false otherwise
- `mark_sent()` from draft succeeds, sets `sent_at`
- `mark_sent()` from sent raises `InvalidTransition`
- `mark_paid()` from draft raises `InvalidTransition` (must go through sent)

**`test_invoice_forms.py`** (~4):

- Due-date-before-issue-date rejected
- Formset with zero rows rejected
- Formset with one valid row accepted
- Negative quantity rejected (PositiveIntegerField does this)

**`test_invoice_views.py`** (~6):

- Unauthenticated → list redirects to login
- Authenticated non-staff → list returns 403
- Staff → create POST valid → creates invoice + items, redirects to detail
- Edit after send → 403
- Send transition POST succeeds, detail shows sent pill + action bar updated
- Public view on draft → 404, on sent → 200

**`test_invoice_pdf.py`** (~2):

- `render_invoice_pdf(invoice)` returns non-empty bytes starting with `%PDF`
- Staff PDF view returns 200 with `application/pdf` Content-Type

### E2E (Playwright) — ~4 new tests

- Create invoice flow: pick customer, add 2 line items, save, land on detail with total calculated
- Transition lifecycle: draft → send → pay; buttons update appropriately at each step
- Public view: open `/invoices/public/<token>/` anonymously, see read-only page, download PDF
- Generate from order: order detail → click "Generate Invoice" → lands on invoice form pre-filled with order's items

### Performance sanity check

List page with 20 invoices + customer annotation should issue ≤ 3 queries (list + count + items annotation). Add `django-debug-toolbar` assertion? Optional. At minimum, verify `select_related("customer")` present.

## Rollout — 7 commits

1. **Models + migrations + factories** — create `apps/invoices/` app, Invoice + InvoiceItem + InvoiceQuerySet, `0001_initial.py`, factories for tests and seed, model unit tests (numbering, totals, state machine, overdue). Register app in `INSTALLED_APPS`.

2. **Forms + formset + admin** — `InvoiceForm` with due/issue validation, `InvoiceItemFormSet` with `validate_min`, Django admin registration with `TabularInline` for items, form tests.

3. **Views + URLs + templates** — list / detail / create / edit / delete CBVs, URL namespace wired, templates (list, detail, form with inline formset HTMX wiring, row partial), `_invoice_status_pill.html`, `_invoice_totals.html`, view tests for CRUD + access control. Sidebar entry added. `file-text` icon registered.

4. **Status transitions** — send/pay/void POST-only views, `mark_sent` / `mark_paid` / `mark_void` methods, `InvalidTransition` handling, detail template action bar (status-dependent button visibility), transition tests.

5. **PDF rendering** — add `weasyprint` to `pyproject.toml`, `apps/invoices/pdf.py::render_invoice_pdf`, `InvoicePdfView` + `invoice_pdf.html` template with print CSS, smoke tests (non-empty PDF bytes, Content-Type check). Document system lib setup in README.

6. **Public view + Order bridge** — `PublicInvoiceView` + `PublicInvoicePdfView` with UUID-token routing, `templates/layouts/public.html` minimal layout, `invoice_public.html`, `GenerateInvoiceFromOrderView` on Orders app + button on Order detail, seed_demo updates (create 15 invoices across statuses). Updated E2E-adjacent tests.

7. **E2E tests** — 4 Playwright tests (create flow, transition lifecycle, public view + PDF, generate-from-order) + verify full E2E suite still passes.

## Open questions

1. **PDF logo source.** Use the existing `static/img/apex-logo.svg`? Or add a dedicated `invoice-logo.png` for print? *Proposed:* use existing SVG; WeasyPrint handles SVG natively.
2. **`Invoice.order` uniqueness.** Should a single Order generate at most one Invoice? *Proposed:* No — allow multiple (e.g. a credit-note pattern could add a second invoice to the same order). Document the assumption in the generate view's `get_or_create`-style logic: "create new each click" not "reuse existing."
3. **Public view rate limit.** Should `/invoices/public/<token>/` be rate-limited to mitigate token-enumeration? *Proposed:* No for v1. UUID4 space is enormous; add `django-ratelimit` only if abuse observed.

## Forward-compatibility notes (for Phase 4c and 5a)

- **Notifications (4c):** When a user transitions an invoice to `sent`, emit a Notification (receiver = customer's staff owner, or all staff — 4c decides). The `mark_sent` hook is a natural emit point. 4b deliberately doesn't send email; 4c owns the send + notification dispatch.
- **Mail (5a):** If Mail ships a "send invoice via email" action, it reuses `render_invoice_pdf` to attach, and the public-token URL to link — no refactor needed in 4b.
- **Overdue transitions:** A future phase can add a management command `mark_overdue_invoices` that flips status, or can keep it derived. Either way, the `display_status` property insulates templates from the choice.
- **Credit notes / refunds:** A `type` field on `Invoice` (with choices `invoice` / `credit_note`) can be added later without touching any current templates — detail/public/PDF would conditionally render.
- **Currency:** Adding `currency = CharField(choices=...)` on `Invoice` is a one-migration future change. Totals still work as long as mixed-currency display is confined to the detail page initially.
