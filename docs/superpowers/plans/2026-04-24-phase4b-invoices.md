# Phase 4b — Invoices Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a dedicated `Invoice` + `InvoiceItem` model pair with staff-gated CRUD, a `DRAFT → SENT → (PAID | VOID)` state machine, auto-generated `INV-YYYY-NNNN` numbering, WeasyPrint-rendered PDF export, a UUID-token public view for sharing with customers, and an optional Order → Invoice bridge.

**Architecture:** New Django app `apps/invoices/` following the established layout from [apps/customers](../../apps/customers/). Invoice header fields + inline formset for line items (HTMX-driven add/remove). Status transitions gated by a small dict-based state machine on the model. PDF rendering isolated in `apps/invoices/pdf.py` using WeasyPrint. Public view is a bare-chrome layout (`templates/layouts/public.html`) so customers don't see the staff dashboard.

**Tech Stack:** Django 5.1 · WeasyPrint (new dep) · HTMX for inline formset rows · pytest · Playwright. One new Python dep (`weasyprint>=62.0`); system libs documented in README.

**Reference spec:** [`docs/superpowers/specs/2026-04-24-phase4b-invoices-design.md`](../specs/2026-04-24-phase4b-invoices-design.md)

**7 commits:**

1. Invoice + InvoiceItem models + migration + factory + unit tests
2. InvoiceForm + InvoiceItemFormSet + admin + form tests
3. CRUD views + URLs + templates + sidebar entry + view tests
4. Status transitions (send/pay/void) + view tests
5. PDF rendering (WeasyPrint) + PDF tests
6. Public view + Order bridge + `templates/layouts/public.html` + seed_demo
7. E2E tests

---

## Pre-flight

- [ ] **Baseline: full suite green on `main` with Phase 4a merged.**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~180 passed.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: ~21 passed (18 pre-4a + 3 Phase 4a).

> **If Phase 4a is not yet merged to `main`:** branch from `phase4a-customers` instead, and adjust the merge-to-main step at the end. Plan is compatible with either starting point.

- [ ] **Install WeasyPrint system libs (one-time dev setup).**

macOS:
```bash
brew install cairo pango gdk-pixbuf libffi
```

Debian/Ubuntu:
```bash
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0
```

Verify: `python -c "import ctypes.util; print(ctypes.util.find_library('pango-1.0'))"` should return a non-empty path.

- [ ] **Create feature branch.**

Run: `git switch -c phase4b-invoices`
Expected: `Switched to a new branch 'phase4b-invoices'`.

---

## Task 1 — Invoice + InvoiceItem models + migration + factory + unit tests

**Files:**

- Create: `apps/invoices/__init__.py` (empty)
- Create: `apps/invoices/apps.py`
- Create: `apps/invoices/models.py`
- Create: `apps/invoices/migrations/__init__.py` (empty)
- Create: `apps/invoices/migrations/0001_initial.py` (generated)
- Create: `apps/invoices/tests/__init__.py` (empty)
- Create: `apps/invoices/tests/factories.py`
- Create: `apps/invoices/tests/test_models.py`
- Modify: `apex/settings/base.py` (register `apps.invoices`)
- Modify: `pyproject.toml` (add `weasyprint` to dependencies)

### Step 1.1 — Create app scaffolding

```bash
mkdir -p apps/invoices/migrations apps/invoices/tests
touch apps/invoices/__init__.py apps/invoices/migrations/__init__.py apps/invoices/tests/__init__.py
```

### Step 1.2 — Create `apps/invoices/apps.py`

```python
from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.invoices"
    label = "invoices"
```

### Step 1.3 — Register app in settings

Open `apex/settings/base.py`. In `INSTALLED_APPS`, insert `"apps.invoices",` after `"apps.customers",`:

```python
INSTALLED_APPS = [
    # ... Django apps ...
    "apps.core",
    "apps.accounts",
    "apps.customers",
    "apps.invoices",    # NEW
    "apps.products",
    "apps.orders",
    "apps.dashboard",
]
```

### Step 1.4 — Add WeasyPrint to pyproject.toml

Open `pyproject.toml`. In `[project].dependencies`, add:

```toml
dependencies = [
  "django>=5.1,<5.2",
  "whitenoise>=6.7",
  "python-dotenv>=1.0",
  "pillow>=11.0",
  "pyotp~=2.9",
  "qrcode~=7.4",
  "weasyprint>=62.0",
]
```

Run: `/Users/silkalns/.local/bin/uv sync 2>&1 | tail -5`
Expected: `Installed weasyprint==<version>` among dependency resolutions.

Smoke-test import:
```bash
/Users/silkalns/.local/bin/uv run python -c "from weasyprint import HTML; print('ok')"
```
Expected: `ok`.

### Step 1.5 — Create the models

`apps/invoices/models.py`:

```python
"""Invoice + InvoiceItem models with state machine and auto-numbering.

State machine: draft -> sent -> (paid | void). Overdue is derived from
(status == "sent" AND due_date < today), never stored.

Invoice.number format: INV-YYYY-NNNN, per-year sequence, assigned on first
save under SELECT FOR UPDATE to serialize concurrent inserts.
"""
import uuid
from decimal import Decimal

from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer


class InvalidTransition(Exception):
    """Raised when an illegal status transition is attempted."""


class InvoiceQuerySet(models.QuerySet):
    def overdue(self):
        return self.filter(status="sent", due_date__lt=timezone.now().date())

    def public_visible(self):
        return self.exclude(status="draft")


class Invoice(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("paid", "Paid"),
        ("void", "Void"),
    ]

    _ALLOWED_TRANSITIONS = {
        "draft": {"sent"},
        "sent": {"paid", "void"},
        "paid": set(),
        "void": set(),
    }

    number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="invoices"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="invoices",
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

    def __str__(self) -> str:
        return self.number or f"Invoice #{self.pk}"

    def get_absolute_url(self) -> str:
        return reverse("invoices:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    def _generate_number(self) -> str:
        year = (self.issue_date or timezone.now().date()).year
        prefix = f"INV-{year}-"
        with transaction.atomic():
            last = (
                Invoice.objects
                .select_for_update()
                .filter(number__startswith=prefix)
                .order_by("-number")
                .first()
            )
            if last:
                seq = int(last.number.split("-")[-1]) + 1
            else:
                seq = 1
            return f"{prefix}{seq:04d}"

    # --- totals (computed from items) ---
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
    def _transition(self, to: str, timestamp_field: str) -> None:
        if to not in self._ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransition(
                f"Cannot transition {self.number} from {self.status} to {to}."
            )
        self.status = to
        setattr(self, timestamp_field, timezone.now())
        self.save(update_fields=["status", timestamp_field, "updated_at"])

    def mark_sent(self) -> None:
        self._transition("sent", "sent_at")

    def mark_paid(self) -> None:
        self._transition("paid", "paid_at")

    def mark_void(self) -> None:
        self._transition("void", "voided_at")


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.description} × {self.quantity}"

    @property
    def amount(self) -> Decimal:
        return (Decimal(self.quantity) * self.unit_price).quantize(Decimal("0.01"))
```

### Step 1.6 — Create the factories

`apps/invoices/tests/factories.py`:

```python
from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.customers.tests.factories import CustomerFactory
from apps.invoices.models import Invoice, InvoiceItem


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice

    customer = factory.SubFactory(CustomerFactory)
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    due_date = factory.LazyFunction(lambda: timezone.now().date() + timedelta(days=30))
    tax_rate = Decimal("10.00")
    notes = ""
    status = "draft"


class InvoiceItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceItem

    invoice = factory.SubFactory(InvoiceFactory)
    description = factory.Faker("sentence", nb_words=4)
    quantity = factory.Faker("pyint", min_value=1, max_value=10)
    unit_price = factory.LazyFunction(lambda: Decimal("99.00"))
```

### Step 1.7 — Write model tests

`apps/invoices/tests/test_models.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.invoices.models import Invoice, InvalidTransition
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db


# ----- Numbering -----

def test_first_invoice_of_year_gets_0001():
    inv = InvoiceFactory(issue_date=date(2026, 6, 1))
    assert inv.number == "INV-2026-0001"


def test_second_invoice_of_year_gets_0002():
    InvoiceFactory(issue_date=date(2026, 6, 1))
    second = InvoiceFactory(issue_date=date(2026, 8, 1))
    assert second.number == "INV-2026-0002"


def test_new_year_resets_sequence():
    InvoiceFactory(issue_date=date(2026, 12, 31))
    next_year = InvoiceFactory(issue_date=date(2027, 1, 1))
    assert next_year.number == "INV-2027-0001"


def test_number_is_immutable_after_create():
    inv = InvoiceFactory()
    original = inv.number
    inv.notes = "edited"
    inv.save()
    inv.refresh_from_db()
    assert inv.number == original


# ----- Totals -----

def test_subtotal_sums_item_amounts():
    inv = InvoiceFactory(tax_rate=Decimal("0"))
    InvoiceItemFactory(invoice=inv, quantity=2, unit_price=Decimal("10.00"))
    InvoiceItemFactory(invoice=inv, quantity=3, unit_price=Decimal("5.50"))
    assert inv.subtotal == Decimal("36.50")


def test_tax_amount_is_rate_percent_of_subtotal():
    inv = InvoiceFactory(tax_rate=Decimal("10"))
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("100.00"))
    assert inv.tax_amount == Decimal("10.00")


def test_total_equals_subtotal_plus_tax():
    inv = InvoiceFactory(tax_rate=Decimal("10"))
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("100.00"))
    assert inv.total == Decimal("110.00")


# ----- Derived status -----

def test_overdue_when_sent_and_past_due():
    inv = InvoiceFactory(status="draft",
                         due_date=timezone.now().date() - timedelta(days=1))
    # Transition to sent
    inv.mark_sent()
    assert inv.is_overdue is True
    assert inv.display_status == "overdue"


def test_not_overdue_when_draft():
    inv = InvoiceFactory(status="draft",
                         due_date=timezone.now().date() - timedelta(days=1))
    assert inv.is_overdue is False
    assert inv.display_status == "draft"


def test_not_overdue_when_paid():
    inv = InvoiceFactory(due_date=timezone.now().date() - timedelta(days=1))
    inv.mark_sent()
    inv.mark_paid()
    assert inv.is_overdue is False
    assert inv.display_status == "paid"


# ----- State machine -----

def test_mark_sent_from_draft_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    assert inv.status == "sent"
    assert inv.sent_at is not None


def test_mark_sent_from_sent_raises():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    with pytest.raises(InvalidTransition):
        inv.mark_sent()


def test_mark_paid_from_draft_raises():
    inv = InvoiceFactory(status="draft")
    with pytest.raises(InvalidTransition):
        inv.mark_paid()


def test_mark_paid_from_sent_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_paid()
    assert inv.status == "paid"
    assert inv.paid_at is not None


def test_mark_void_from_sent_succeeds():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_void()
    assert inv.status == "void"
    assert inv.voided_at is not None


def test_paid_is_terminal():
    inv = InvoiceFactory(status="draft")
    inv.mark_sent()
    inv.mark_paid()
    with pytest.raises(InvalidTransition):
        inv.mark_void()


# ----- Public token -----

def test_public_token_assigned_on_create():
    inv = InvoiceFactory()
    assert inv.public_token is not None


def test_public_token_is_unique():
    a = InvoiceFactory()
    b = InvoiceFactory()
    assert a.public_token != b.public_token
```

### Step 1.8 — Generate and apply migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py makemigrations invoices 2>&1 | tail -10`
Expected: `Migrations for 'invoices': apps/invoices/migrations/0001_initial.py + Create model Invoice + Create model InvoiceItem`.

Run: `/Users/silkalns/.local/bin/uv run python manage.py migrate invoices 2>&1 | tail -5`
Expected: `Applying invoices.0001_initial... OK`.

### Step 1.9 — Run model tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/test_models.py -v 2>&1 | tail -30`
Expected: 18 passed.

### Step 1.10 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~198 passed (~180 prior + 18 new).

### Step 1.11 — Commit

```bash
git add apps/invoices/ apex/settings/base.py pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
feat(invoices): Invoice + InvoiceItem models with state machine

New apps/invoices/ app. Invoice carries auto-generated INV-YYYY-NNNN
numbers assigned under SELECT FOR UPDATE for safe concurrent inserts.
State machine: draft -> sent -> (paid | void); overdue is derived.
InvoiceItem is a simple child with PROTECT on Customer and SET_NULL
on Order. WeasyPrint added as a dependency (used in task 5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — InvoiceForm + InvoiceItemFormSet + admin + form tests

**Files:**

- Create: `apps/invoices/forms.py`
- Create: `apps/invoices/admin.py`
- Create: `apps/invoices/tests/test_forms.py`

### Step 2.1 — Create the form and formset

`apps/invoices/forms.py`:

```python
from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import BASE_INPUT
from apps.invoices.models import Invoice, InvoiceItem


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["customer", "order", "issue_date", "due_date", "tax_rate", "notes"]
        widgets = {
            "customer":   forms.Select(attrs={"class": BASE_INPUT}),
            "order":      forms.Select(attrs={"class": BASE_INPUT}),
            "issue_date": forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "due_date":   forms.DateInput(attrs={"type": "date", "class": BASE_INPUT}),
            "tax_rate":   forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01", "min": 0}),
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
        "unit_price":  forms.NumberInput(attrs={"class": BASE_INPUT, "step": "0.01", "min": 0}),
    },
)
```

> **Note:** `apps/core/forms.py` already exports `BASE_INPUT` — the Tailwind class string used by every existing form (Products, Orders, Customers). Confirm with `grep -n BASE_INPUT apps/core/forms.py`. If it's missing, the Customers phase would not have passed its tests, so this is a given.

### Step 2.2 — Register admin

`apps/invoices/admin.py`:

```python
from django.contrib import admin

from apps.invoices.models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ("description", "quantity", "unit_price")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "customer", "issue_date", "due_date", "status", "total")
    list_filter = ("status",)
    search_fields = ("number", "customer__name", "customer__email")
    readonly_fields = ("number", "public_token", "sent_at", "paid_at", "voided_at",
                       "created_at", "updated_at")
    inlines = [InvoiceItemInline]
    date_hierarchy = "issue_date"
```

### Step 2.3 — Write form tests

`apps/invoices/tests/test_forms.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers.tests.factories import CustomerFactory
from apps.invoices.forms import InvoiceForm, InvoiceItemFormSet
from apps.invoices.models import Invoice
from apps.invoices.tests.factories import InvoiceFactory

pytestmark = pytest.mark.django_db


def _base_payload(customer, **overrides):
    payload = {
        "customer": customer.pk,
        "order": "",
        "issue_date": date(2026, 6, 1).isoformat(),
        "due_date": date(2026, 6, 30).isoformat(),
        "tax_rate": "10.00",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def test_invoice_form_valid_minimal():
    c = CustomerFactory()
    form = InvoiceForm(data=_base_payload(c))
    assert form.is_valid(), form.errors


def test_due_date_before_issue_date_rejected():
    c = CustomerFactory()
    form = InvoiceForm(data=_base_payload(
        c,
        issue_date=date(2026, 6, 30).isoformat(),
        due_date=date(2026, 6, 1).isoformat(),
    ))
    assert not form.is_valid()
    assert "Due date cannot be before issue date." in str(form.errors)


# ----- Formset -----

def _formset_payload(prefix="items", *, rows):
    """Build formset management + row payload."""
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "1",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for i, row in enumerate(rows):
        for key, value in row.items():
            data[f"{prefix}-{i}-{key}"] = value
    return data


def test_formset_with_one_valid_row_accepted():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[{
        "description": "Consulting",
        "quantity": "2",
        "unit_price": "150.00",
    }])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert fs.is_valid(), fs.errors


def test_formset_with_zero_rows_rejected():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert not fs.is_valid()


def test_formset_negative_quantity_rejected():
    inv = InvoiceFactory()
    data = _formset_payload(rows=[{
        "description": "Bad row",
        "quantity": "-1",
        "unit_price": "10.00",
    }])
    fs = InvoiceItemFormSet(data, instance=inv)
    assert not fs.is_valid()
```

### Step 2.4 — Run form tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/test_forms.py -v 2>&1 | tail -15`
Expected: 5 passed.

### Step 2.5 — Verify admin loads

Run: `/Users/silkalns/.local/bin/uv run python manage.py check 2>&1 | tail -5`
Expected: `System check identified no issues (0 silenced).`

### Step 2.6 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~203 passed.

### Step 2.7 — Commit

```bash
git add apps/invoices/forms.py apps/invoices/admin.py apps/invoices/tests/test_forms.py
git commit -m "$(cat <<'EOF'
feat(invoices): InvoiceForm + item formset + admin inline

InvoiceItemFormSet uses validate_min=True to enforce at least one
line item. InvoiceForm.clean rejects due_date < issue_date. Admin
exposes Invoice with the item inline for operator convenience.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — CRUD views + URLs + templates + sidebar + view tests

**Files:**

- Create: `apps/invoices/views.py` (list/detail/create/edit/delete + HTMX row-add)
- Create: `apps/invoices/urls.py`
- Modify: `apex/urls.py` (include invoices)
- Create: `templates/invoices/invoice_list.html`
- Create: `templates/invoices/invoice_detail.html`
- Create: `templates/invoices/invoice_form.html`
- Create: `templates/invoices/_invoice_status_pill.html`
- Create: `templates/invoices/_invoice_item_row.html`
- Create: `templates/invoices/_invoice_totals.html`
- Modify: `apps/core/navigation.py` (add NavItem)
- Modify: `apps/core/templatetags/apex.py` (add `file-text` icon)
- Create: `apps/invoices/tests/test_views.py`

### Step 3.1 — Create CRUD views

`apps/invoices/views.py`:

```python
"""Invoice CRUD + HTMX row-add + status transitions (task 4) + PDF (task 5) + public (task 6)."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin, StaffRequiredMixin
from apps.core.mixins import BreadcrumbsMixin
from apps.invoices.forms import InvoiceForm, InvoiceItemFormSet
from apps.invoices.models import Invoice, InvoiceItem


class InvoiceListView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Invoice
    paginate_by = 20
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    breadcrumb_title = "Invoices"

    def get_queryset(self):
        return (
            Invoice.objects
            .select_related("customer")
            .annotate(items_count=models.Count("items", distinct=True))
            .order_by("-issue_date", "-number")
        )


class InvoiceDetailView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin, DetailView):
    model = Invoice
    template_name = "invoices/invoice_detail.html"
    context_object_name = "invoice"

    def get_breadcrumb_title(self):
        return self.object.number

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        return ctx


class _InvoiceFormMixin:
    """Shared form_valid that handles the inline formset transactionally."""

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context["formset"]
        if not formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, f"Invoice {self.object.number} saved.")
        return redirect(self.object.get_absolute_url())


class InvoiceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        _InvoiceFormMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/invoice_form.html"
    breadcrumb_title = "New invoice"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["formset"] = InvoiceItemFormSet(self.request.POST, prefix="items")
        else:
            ctx["formset"] = InvoiceItemFormSet(prefix="items")
        return ctx


class InvoiceUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        _InvoiceFormMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoices/invoice_form.html"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.number}"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status != "draft":
            return HttpResponseForbidden("Only draft invoices can be edited.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx["formset"] = InvoiceItemFormSet(
                self.request.POST, instance=self.object, prefix="items"
            )
        else:
            ctx["formset"] = InvoiceItemFormSet(instance=self.object, prefix="items")
        return ctx


class InvoiceDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, View):
    """POST-only. Only drafts can be deleted."""

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if invoice.status != "draft":
            return HttpResponseForbidden("Only draft invoices can be deleted.")
        number = invoice.number
        invoice.delete()
        messages.success(request, f"Draft invoice {number} deleted.")
        return redirect("invoices:list")


class InvoiceItemAddRowView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    """HTMX helper that returns a blank item row with the given index."""

    def get(self, request):
        try:
            index = int(request.GET.get("index", 0))
        except (TypeError, ValueError):
            index = 0
        formset = InvoiceItemFormSet(prefix="items")
        # Build an unbound form at the requested index
        empty_form = formset.empty_form
        empty_form.prefix = f"items-{index}"
        return render(request, "invoices/_invoice_item_row.html", {"form": empty_form})
```

### Step 3.2 — Create URLs

`apps/invoices/urls.py`:

```python
from django.urls import path

from apps.invoices import views

app_name = "invoices"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="list"),
    path("new/", views.InvoiceCreateView.as_view(), name="create"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.InvoiceUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.InvoiceDeleteView.as_view(), name="delete"),
    path("items/add-row/", views.InvoiceItemAddRowView.as_view(), name="add_row"),
    # Task 4 adds: send, pay, void
    # Task 5 adds: pdf
    # Task 6 adds: public, public_pdf
]
```

### Step 3.3 — Wire URLs in apex/urls.py

Open `apex/urls.py`. Add alongside other app includes:

```python
path("invoices/", include("apps.invoices.urls")),
```

Place between the `customers` include and the `orders` include for consistency with sidebar grouping.

### Step 3.4 — Add sidebar entry

Open `apps/core/navigation.py`. Locate `NAV_ITEMS`. Insert after the Customers entry, before Orders:

```python
NavItem("Invoices", "invoices:list", "file-text",
        keywords=("billing", "finance"), group="Commerce",
        requires_staff=True),
```

### Step 3.5 — Register the `file-text` icon

Open `apps/core/templatetags/apex.py`. Find the `ICONS` dict. Add:

```python
"file-text": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" /><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75h6m-6 3h6m-6 3h3" /></svg>',
```

### Step 3.6 — Templates

**`templates/invoices/_invoice_status_pill.html`:**

```django
{% load apex %}
{% with s=status %}
  {% if s == "draft" %}
    <span class="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">Draft</span>
  {% elif s == "sent" %}
    <span class="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">Sent</span>
  {% elif s == "overdue" %}
    <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/30 dark:text-red-300">Overdue</span>
  {% elif s == "paid" %}
    <span class="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-300">Paid</span>
  {% elif s == "void" %}
    <span class="inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-500 line-through dark:bg-zinc-800 dark:text-zinc-500">Void</span>
  {% endif %}
{% endwith %}
```

**`templates/invoices/_invoice_totals.html`:**

```django
<div class="flex flex-col gap-1 text-sm">
  <div class="flex justify-between">
    <span class="text-muted-foreground">Subtotal</span>
    <span>${{ invoice.subtotal|floatformat:2 }}</span>
  </div>
  <div class="flex justify-between">
    <span class="text-muted-foreground">Tax ({{ invoice.tax_rate }}%)</span>
    <span>${{ invoice.tax_amount|floatformat:2 }}</span>
  </div>
  <div class="flex justify-between border-t border-border pt-2 font-semibold">
    <span>Total</span>
    <span>${{ invoice.total|floatformat:2 }}</span>
  </div>
</div>
```

**`templates/invoices/_invoice_item_row.html`:**

```django
<tr x-data="{ removed: false }" x-show="!removed" class="border-b border-border">
  <td class="p-2">{{ form.description }}</td>
  <td class="p-2 w-24">{{ form.quantity }}</td>
  <td class="p-2 w-32">{{ form.unit_price }}</td>
  <td class="p-2 w-12 text-right">
    {% if form.instance.pk %}{{ form.id }}{% endif %}
    <label class="hidden">{{ form.DELETE }}</label>
    <button type="button"
            @click="removed = true; $refs.del.checked = true"
            class="text-muted-foreground hover:text-destructive">×</button>
    <input x-ref="del" type="checkbox" name="{{ form.DELETE.html_name }}" class="hidden">
  </td>
</tr>
```

**`templates/invoices/invoice_list.html`:**

```django
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}Invoices · Apex{% endblock %}

{% block content %}
<div class="flex items-center justify-between">
  <h1 class="text-2xl font-semibold">Invoices</h1>
  <a href="{% url 'invoices:create' %}"
     class="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
    {% icon "plus" %} New invoice
  </a>
</div>

<div class="mt-6 overflow-hidden rounded-lg border border-border bg-card">
  <table class="w-full text-sm">
    <thead class="bg-muted/50 text-left text-xs uppercase tracking-wide text-muted-foreground">
      <tr>
        <th class="px-4 py-3">Number</th>
        <th class="px-4 py-3">Customer</th>
        <th class="px-4 py-3">Issue</th>
        <th class="px-4 py-3">Due</th>
        <th class="px-4 py-3 text-right">Total</th>
        <th class="px-4 py-3">Status</th>
      </tr>
    </thead>
    <tbody>
      {% for invoice in invoices %}
      <tr class="border-t border-border hover:bg-muted/30">
        <td class="px-4 py-3 font-mono">
          <a href="{{ invoice.get_absolute_url }}" class="hover:underline">{{ invoice.number }}</a>
        </td>
        <td class="px-4 py-3">{{ invoice.customer.name }}</td>
        <td class="px-4 py-3">{{ invoice.issue_date|date:"M j, Y" }}</td>
        <td class="px-4 py-3">{{ invoice.due_date|date:"M j, Y" }}</td>
        <td class="px-4 py-3 text-right">${{ invoice.total|floatformat:2 }}</td>
        <td class="px-4 py-3">
          {% include "invoices/_invoice_status_pill.html" with status=invoice.display_status %}
        </td>
      </tr>
      {% empty %}
      <tr><td colspan="6" class="p-8 text-center text-muted-foreground">No invoices yet.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

{% include "partials/pagination.html" %}
{% endblock %}
```

**`templates/invoices/invoice_detail.html`:**

```django
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}{{ invoice.number }} · Apex{% endblock %}

{% block content %}
<div class="flex items-start justify-between">
  <div>
    <div class="flex items-center gap-3">
      <h1 class="font-mono text-2xl font-semibold">{{ invoice.number }}</h1>
      {% include "invoices/_invoice_status_pill.html" with status=invoice.display_status %}
    </div>
    <p class="mt-1 text-sm text-muted-foreground">
      Issued {{ invoice.issue_date|date:"M j, Y" }} · Due {{ invoice.due_date|date:"M j, Y" }}
    </p>
  </div>
  <div class="flex gap-2">
    {% if invoice.status == "draft" %}
      <a href="{% url 'invoices:edit' invoice.pk %}"
         class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">Edit</a>
      {# Task 4 wires send/pay/void; task 5 wires PDF; task 6 wires public #}
    {% endif %}
  </div>
</div>

<div class="mt-6 grid gap-6 lg:grid-cols-3">
  <div class="lg:col-span-2 rounded-lg border border-border bg-card p-6">
    <h2 class="text-sm font-semibold text-muted-foreground">Bill to</h2>
    <p class="mt-1 font-medium">{{ invoice.customer.name }}</p>
    {% if invoice.customer.company %}<p class="text-sm">{{ invoice.customer.company }}</p>{% endif %}
    <p class="text-sm text-muted-foreground">{{ invoice.customer.email }}</p>

    <h2 class="mt-6 text-sm font-semibold text-muted-foreground">Line items</h2>
    <table class="mt-2 w-full text-sm">
      <thead class="border-b border-border text-left text-xs uppercase text-muted-foreground">
        <tr>
          <th class="py-2">Description</th>
          <th class="py-2 w-20 text-right">Qty</th>
          <th class="py-2 w-28 text-right">Unit price</th>
          <th class="py-2 w-28 text-right">Amount</th>
        </tr>
      </thead>
      <tbody>
        {% for item in items %}
        <tr class="border-b border-border/60">
          <td class="py-2">{{ item.description }}</td>
          <td class="py-2 text-right">{{ item.quantity }}</td>
          <td class="py-2 text-right">${{ item.unit_price|floatformat:2 }}</td>
          <td class="py-2 text-right">${{ item.amount|floatformat:2 }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    {% if invoice.notes %}
    <div class="mt-6 rounded-md bg-muted/40 p-4 text-sm">
      <p class="font-semibold text-muted-foreground">Notes</p>
      <p class="mt-1 whitespace-pre-line">{{ invoice.notes }}</p>
    </div>
    {% endif %}
  </div>

  <aside class="rounded-lg border border-border bg-card p-6">
    {% include "invoices/_invoice_totals.html" %}
  </aside>
</div>
{% endblock %}
```

**`templates/invoices/invoice_form.html`:**

```django
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}{{ view.breadcrumb_title }} · Apex{% endblock %}

{% block content %}
<h1 class="text-2xl font-semibold">{{ view.breadcrumb_title }}</h1>

<form method="post" class="mt-6 space-y-6">
  {% csrf_token %}

  <div class="grid gap-4 rounded-lg border border-border bg-card p-6 md:grid-cols-2">
    <label class="block text-sm">
      <span class="font-medium">Customer</span>
      {{ form.customer }}
      {{ form.customer.errors }}
    </label>
    <label class="block text-sm">
      <span class="font-medium">Order (optional)</span>
      {{ form.order }}
      {{ form.order.errors }}
    </label>
    <label class="block text-sm">
      <span class="font-medium">Issue date</span>
      {{ form.issue_date }}
      {{ form.issue_date.errors }}
    </label>
    <label class="block text-sm">
      <span class="font-medium">Due date</span>
      {{ form.due_date }}
      {{ form.due_date.errors }}
    </label>
    <label class="block text-sm">
      <span class="font-medium">Tax rate (%)</span>
      {{ form.tax_rate }}
      {{ form.tax_rate.errors }}
    </label>
    <label class="block text-sm md:col-span-2">
      <span class="font-medium">Notes</span>
      {{ form.notes }}
    </label>
  </div>

  <div class="rounded-lg border border-border bg-card p-6">
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold">Line items</h2>
      <button type="button"
              hx-get="{% url 'invoices:add_row' %}"
              hx-include="[name='items-TOTAL_FORMS']"
              hx-vals='js:{"index": document.getElementsByName("items-TOTAL_FORMS")[0].value}'
              hx-target="#invoice-items"
              hx-swap="beforeend"
              @htmx:after-request="document.getElementsByName('items-TOTAL_FORMS')[0].value = parseInt(document.getElementsByName('items-TOTAL_FORMS')[0].value) + 1"
              class="rounded-md border border-border bg-background px-3 py-1.5 text-xs">
        + Add row
      </button>
    </div>
    {{ formset.non_form_errors }}
    <table class="mt-3 w-full text-sm">
      <thead class="text-left text-xs uppercase text-muted-foreground">
        <tr>
          <th class="p-2">Description</th>
          <th class="p-2">Qty</th>
          <th class="p-2">Unit price</th>
          <th class="p-2"></th>
        </tr>
      </thead>
      <tbody id="invoice-items">
        {{ formset.management_form }}
        {% for form in formset %}
          {% include "invoices/_invoice_item_row.html" %}
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="flex justify-end gap-2">
    <a href="{% url 'invoices:list' %}" class="rounded-md border border-border px-4 py-2 text-sm">Cancel</a>
    <button type="submit" class="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">Save</button>
  </div>
</form>
{% endblock %}
```

> **HTMX add-row note:** The `@htmx:after-request` handler increments `TOTAL_FORMS` after each successful row insert. This is the minimal working wiring; if Alpine plugins feel cleaner in your codebase later, refactor is trivial.

### Step 3.7 — Write view tests

`apps/invoices/tests/test_views.py`:

```python
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.customers.tests.factories import CustomerFactory
from apps.invoices.models import Invoice
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user(db):
    return UserFactory(is_staff=True, email_verified=True)


@pytest.fixture
def regular_user(db):
    return UserFactory(is_staff=False, email_verified=True)


# ----- Access control -----

def test_list_redirects_anonymous(client):
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 302
    assert "login" in r.url


def test_list_forbidden_for_non_staff(client, regular_user):
    client.force_login(regular_user)
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 403


def test_list_ok_for_staff(client, staff_user):
    client.force_login(staff_user)
    InvoiceFactory.create_batch(3)
    r = client.get(reverse("invoices:list"))
    assert r.status_code == 200
    assert b"INV-" in r.content


# ----- Create -----

def test_create_invoice_flow(client, staff_user):
    client.force_login(staff_user)
    customer = CustomerFactory()
    payload = {
        "customer": customer.pk,
        "order": "",
        "issue_date": date(2026, 6, 1).isoformat(),
        "due_date": date(2026, 6, 30).isoformat(),
        "tax_rate": "10.00",
        "notes": "Thanks!",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "1",
        "items-MAX_NUM_FORMS": "1000",
        "items-0-description": "Consulting",
        "items-0-quantity": "2",
        "items-0-unit_price": "150.00",
    }
    r = client.post(reverse("invoices:create"), data=payload)
    assert r.status_code == 302
    inv = Invoice.objects.get()
    assert inv.number.startswith("INV-2026-")
    assert inv.items.count() == 1
    assert inv.subtotal == Decimal("300.00")


# ----- Detail -----

def test_detail_ok_for_staff(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv, quantity=1, unit_price=Decimal("50.00"))
    r = client.get(reverse("invoices:detail", args=[inv.pk]))
    assert r.status_code == 200
    assert inv.number.encode() in r.content


# ----- Edit -----

def test_edit_draft_allowed(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:edit", args=[inv.pk]))
    assert r.status_code == 200


def test_edit_sent_forbidden(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.get(reverse("invoices:edit", args=[inv.pk]))
    assert r.status_code == 403


# ----- Delete -----

def test_delete_draft_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.post(reverse("invoices:delete", args=[inv.pk]))
    assert r.status_code == 302
    assert not Invoice.objects.filter(pk=inv.pk).exists()


def test_delete_sent_forbidden(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:delete", args=[inv.pk]))
    assert r.status_code == 403
    assert Invoice.objects.filter(pk=inv.pk).exists()


# ----- HTMX row add -----

def test_add_row_returns_blank_row(client, staff_user):
    client.force_login(staff_user)
    r = client.get(reverse("invoices:add_row") + "?index=2")
    assert r.status_code == 200
    assert b"items-2-description" in r.content
```

### Step 3.8 — Run view tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/test_views.py -v 2>&1 | tail -25`
Expected: 10 passed.

### Step 3.9 — Smoke-test in browser (optional but recommended)

Start server: `/Users/silkalns/.local/bin/uv run python manage.py runserver`
Visit `http://localhost:8000/invoices/` — should show an empty list with "New invoice" button.
Click "New invoice" → form loads. Add a row, fill, submit → lands on detail.

### Step 3.10 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~213 passed.

### Step 3.11 — Commit

```bash
git add apps/invoices/ apex/urls.py apps/core/navigation.py apps/core/templatetags/apex.py templates/invoices/
git commit -m "$(cat <<'EOF'
feat(invoices): list/detail/create/edit/delete views + templates

Full staff-gated CRUD with inline InvoiceItemFormSet. HTMX-driven
row add via apps.invoices.views.InvoiceItemAddRowView. Edit/delete
gated to drafts only. Sidebar entry under Commerce; file-text icon
registered in the apex templatetag ICONS dict.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Status transitions (send/pay/void)

**Files:**

- Modify: `apps/invoices/views.py` (add `InvoiceSendView`, `InvoicePayView`, `InvoiceVoidView`)
- Modify: `apps/invoices/urls.py` (wire 3 new routes)
- Modify: `templates/invoices/invoice_detail.html` (status-dependent action bar)
- Modify: `apps/invoices/tests/test_views.py` (append transition tests)

### Step 4.1 — Append transition views

At the bottom of `apps/invoices/views.py`:

```python
from apps.invoices.models import InvalidTransition


class _TransitionView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      StaffRequiredMixin, View):
    http_method_names = ["post"]
    action = ""  # subclasses override
    success_msg = ""

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        method = getattr(invoice, f"mark_{self.action}")
        try:
            method()
        except InvalidTransition as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, self.success_msg.format(number=invoice.number))
        return redirect(invoice.get_absolute_url())


class InvoiceSendView(_TransitionView):
    action = "sent"
    success_msg = "Invoice {number} marked as sent."


class InvoicePayView(_TransitionView):
    action = "paid"
    success_msg = "Invoice {number} marked as paid."


class InvoiceVoidView(_TransitionView):
    action = "void"
    success_msg = "Invoice {number} voided."
```

### Step 4.2 — Wire URLs

Open `apps/invoices/urls.py`, add:

```python
path("<int:pk>/send/", views.InvoiceSendView.as_view(), name="send"),
path("<int:pk>/pay/", views.InvoicePayView.as_view(), name="pay"),
path("<int:pk>/void/", views.InvoiceVoidView.as_view(), name="void"),
```

### Step 4.3 — Add action bar to detail template

In `templates/invoices/invoice_detail.html`, replace the `<div class="flex gap-2">` block with:

```django
<div class="flex gap-2">
  {% if invoice.status == "draft" %}
    <a href="{% url 'invoices:edit' invoice.pk %}"
       class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">Edit</a>
    <form method="post" action="{% url 'invoices:send' invoice.pk %}">{% csrf_token %}
      <button class="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">Send</button>
    </form>
    <form method="post" action="{% url 'invoices:delete' invoice.pk %}"
          onsubmit="return confirm('Delete draft {{ invoice.number }}?');">{% csrf_token %}
      <button class="inline-flex items-center gap-2 rounded-md border border-destructive/50 bg-background px-3 py-2 text-sm text-destructive">Delete</button>
    </form>
  {% elif invoice.status == "sent" %}
    <form method="post" action="{% url 'invoices:pay' invoice.pk %}">{% csrf_token %}
      <button class="inline-flex items-center gap-2 rounded-md bg-green-600 px-3 py-2 text-sm font-medium text-white hover:bg-green-700">Mark paid</button>
    </form>
    <form method="post" action="{% url 'invoices:void' invoice.pk %}"
          onsubmit="return confirm('Void {{ invoice.number }}? This cannot be undone.');">{% csrf_token %}
      <button class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">Void</button>
    </form>
  {% endif %}
</div>
```

### Step 4.4 — Append transition tests

Append to `apps/invoices/tests/test_views.py`:

```python
# ----- Transitions -----

def test_send_draft_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    r = client.post(reverse("invoices:send", args=[inv.pk]))
    assert r.status_code == 302
    inv.refresh_from_db()
    assert inv.status == "sent"


def test_send_already_sent_flashes_error(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:send", args=[inv.pk]), follow=True)
    assert r.status_code == 200
    msgs = list(r.context["messages"])
    assert any("Cannot transition" in str(m) for m in msgs)


def test_pay_sent_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:pay", args=[inv.pk]))
    inv.refresh_from_db()
    assert inv.status == "paid"


def test_void_sent_ok(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.post(reverse("invoices:void", args=[inv.pk]))
    inv.refresh_from_db()
    assert inv.status == "void"


def test_pay_draft_flashes_error(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.post(reverse("invoices:pay", args=[inv.pk]), follow=True)
    inv.refresh_from_db()
    assert inv.status == "draft"
    msgs = list(r.context["messages"])
    assert any("Cannot transition" in str(m) for m in msgs)


def test_transition_get_returns_405(client, staff_user):
    client.force_login(staff_user)
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:send", args=[inv.pk]))
    assert r.status_code == 405
```

### Step 4.5 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/test_views.py -v 2>&1 | tail -25`
Expected: 16 passed (10 prior + 6 new).

### Step 4.6 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~219 passed.

### Step 4.7 — Commit

```bash
git add apps/invoices/views.py apps/invoices/urls.py apps/invoices/tests/test_views.py templates/invoices/invoice_detail.html
git commit -m "$(cat <<'EOF'
feat(invoices): status transitions (send/pay/void) + action bar

POST-only transition views sharing a small _TransitionView base.
Illegal transitions surface as messages.error; legal ones redirect
to detail with a success flash. Detail template's action bar is
status-dependent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — PDF rendering (WeasyPrint)

**Files:**

- Create: `apps/invoices/pdf.py`
- Modify: `apps/invoices/views.py` (add `InvoicePdfView`)
- Modify: `apps/invoices/urls.py` (wire pdf route)
- Create: `templates/invoices/invoice_pdf.html`
- Modify: `templates/invoices/invoice_detail.html` (add "Download PDF" button)
- Create: `apps/invoices/tests/test_pdf.py`
- Modify: `README.md` (document system lib setup)

### Step 5.1 — PDF render helper

`apps/invoices/pdf.py`:

```python
"""WeasyPrint-backed PDF rendering for invoices.

Isolated in its own module so the import cost (~50ms) is only paid
when PDF generation is actually requested, and so tests can mock
`render_invoice_pdf` cleanly without stubbing Django's template loader.
"""
from django.http import HttpRequest
from django.template.loader import render_to_string


def render_invoice_pdf(invoice, *, request: HttpRequest | None = None) -> bytes:
    # Lazy import — WeasyPrint triggers cairo/pango load at import time
    from weasyprint import HTML

    html_str = render_to_string(
        "invoices/invoice_pdf.html",
        {"invoice": invoice, "items": invoice.items.all()},
        request=request,
    )
    base_url = request.build_absolute_uri("/") if request else None
    return HTML(string=html_str, base_url=base_url).write_pdf()
```

### Step 5.2 — PDF view

Append to `apps/invoices/views.py`:

```python
from django.http import HttpResponse
from apps.invoices.pdf import render_invoice_pdf


class InvoicePdfView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                     StaffRequiredMixin, View):
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        pdf = render_invoice_pdf(invoice, request=request)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.number}.pdf"'
        )
        return response
```

### Step 5.3 — Wire URL

Add to `apps/invoices/urls.py`:

```python
path("<int:pk>/pdf/", views.InvoicePdfView.as_view(), name="pdf"),
```

### Step 5.4 — PDF template

`templates/invoices/invoice_pdf.html`:

```django
{% load static %}
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ invoice.number }}</title>
<style>
  @page { size: A4; margin: 1.5cm; }
  * { font-family: "Helvetica", "Arial", sans-serif; color: #222; }
  body { font-size: 11pt; }
  h1 { font-size: 22pt; margin: 0; letter-spacing: -0.02em; }
  .muted { color: #666; font-size: 9pt; }
  table { width: 100%; border-collapse: collapse; margin-top: 1em; }
  th, td { padding: 6px 8px; text-align: left; }
  th { border-bottom: 2px solid #222; font-size: 9pt; text-transform: uppercase; letter-spacing: 0.05em; }
  td { border-bottom: 1px solid #ddd; }
  .right { text-align: right; }
  .totals { margin-top: 1.5em; margin-left: auto; width: 40%; }
  .totals div { display: flex; justify-content: space-between; padding: 4px 0; }
  .totals .grand { border-top: 2px solid #222; padding-top: 8px; font-size: 13pt; font-weight: bold; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 9pt; font-weight: 600; }
  .pill-draft { background: #eee; color: #555; }
  .pill-sent { background: #dbeafe; color: #1e40af; }
  .pill-paid { background: #dcfce7; color: #166534; }
  .pill-void { background: #f4f4f5; color: #71717a; text-decoration: line-through; }
  .pill-overdue { background: #fee2e2; color: #991b1b; }
  header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 2em; }
</style>
</head>
<body>
<header>
  <div>
    <h1>Invoice</h1>
    <p class="muted">{{ invoice.number }}</p>
  </div>
  <div class="right">
    <span class="pill pill-{{ invoice.display_status }}">{{ invoice.display_status|upper }}</span>
  </div>
</header>

<div style="display:flex; gap:2em;">
  <div style="flex:1;">
    <p class="muted">Bill to</p>
    <p><strong>{{ invoice.customer.name }}</strong></p>
    {% if invoice.customer.company %}<p>{{ invoice.customer.company }}</p>{% endif %}
    <p class="muted">{{ invoice.customer.email }}</p>
    {% if invoice.customer.address %}<p>{{ invoice.customer.address }}, {{ invoice.customer.city }}</p>{% endif %}
  </div>
  <div style="flex:1;" class="right">
    <p class="muted">Issue date</p>
    <p>{{ invoice.issue_date|date:"F j, Y" }}</p>
    <p class="muted">Due date</p>
    <p>{{ invoice.due_date|date:"F j, Y" }}</p>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Description</th>
      <th class="right">Qty</th>
      <th class="right">Unit price</th>
      <th class="right">Amount</th>
    </tr>
  </thead>
  <tbody>
    {% for item in items %}
    <tr>
      <td>{{ item.description }}</td>
      <td class="right">{{ item.quantity }}</td>
      <td class="right">${{ item.unit_price|floatformat:2 }}</td>
      <td class="right">${{ item.amount|floatformat:2 }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div class="totals">
  <div><span class="muted">Subtotal</span><span>${{ invoice.subtotal|floatformat:2 }}</span></div>
  <div><span class="muted">Tax ({{ invoice.tax_rate }}%)</span><span>${{ invoice.tax_amount|floatformat:2 }}</span></div>
  <div class="grand"><span>Total</span><span>${{ invoice.total|floatformat:2 }}</span></div>
</div>

{% if invoice.notes %}
<p class="muted" style="margin-top:3em;">Notes</p>
<p>{{ invoice.notes|linebreaksbr }}</p>
{% endif %}
</body>
</html>
```

### Step 5.5 — Add "Download PDF" button to detail

In `templates/invoices/invoice_detail.html`, inside the action bar `<div class="flex gap-2">`, as the first entry (always visible):

```django
<a href="{% url 'invoices:pdf' invoice.pk %}"
   class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
  {% icon "download" %} PDF
</a>
```

Ensure `download` icon exists in `apps/core/templatetags/apex.py::ICONS`. If missing, add:

```python
"download": '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>',
```

### Step 5.6 — PDF tests

`apps/invoices/tests/test_pdf.py`:

```python
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.invoices.pdf import render_invoice_pdf
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

pytestmark = pytest.mark.django_db


def test_render_invoice_pdf_returns_pdf_bytes():
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv, quantity=2, unit_price=Decimal("25.00"))
    pdf = render_invoice_pdf(inv)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000  # non-trivial content


def test_pdf_view_returns_pdf_attachment(client):
    user = UserFactory(is_staff=True, email_verified=True)
    client.force_login(user)
    inv = InvoiceFactory()
    InvoiceItemFactory(invoice=inv)
    r = client.get(reverse("invoices:pdf", args=[inv.pk]))
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert inv.number in r["Content-Disposition"]
    assert r.content[:4] == b"%PDF"


def test_pdf_view_requires_staff(client):
    user = UserFactory(is_staff=False, email_verified=True)
    client.force_login(user)
    inv = InvoiceFactory()
    r = client.get(reverse("invoices:pdf", args=[inv.pk]))
    assert r.status_code == 403
```

### Step 5.7 — Document system libs in README

Open `README.md`. In the `## Requirements` section, append:

```markdown
- **WeasyPrint system libraries** (for invoice PDF export):
  - macOS: `brew install cairo pango gdk-pixbuf libffi`
  - Debian/Ubuntu: `apt-get install libpango-1.0-0 libpangoft2-1.0-0`
```

### Step 5.8 — Run PDF tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/test_pdf.py -v 2>&1 | tail -15`
Expected: 3 passed.

> **If tests fail with `OSError: cannot load library 'libpango-1.0...'`:** system libs aren't on PATH. Re-run the `brew install` / `apt-get install` from pre-flight. On macOS, you may need `export DYLD_LIBRARY_PATH=/opt/homebrew/lib` or install via `pip` inside a venv with libs already exposed.

### Step 5.9 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~222 passed.

### Step 5.10 — Commit

```bash
git add apps/invoices/pdf.py apps/invoices/views.py apps/invoices/urls.py apps/invoices/tests/test_pdf.py templates/invoices/ README.md apps/core/templatetags/apex.py
git commit -m "$(cat <<'EOF'
feat(invoices): WeasyPrint PDF export

Staff-gated PDF endpoint renders invoices/invoice_pdf.html via
WeasyPrint. Template uses print-oriented CSS (A4 page, 1.5cm margin,
Helvetica) independent of Tailwind. System lib setup documented in
README Requirements section.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Public view + Order bridge + seed_demo

**Files:**

- Modify: `apps/invoices/views.py` (add `PublicInvoiceView`, `PublicInvoicePdfView`)
- Modify: `apps/invoices/urls.py` (wire 2 public routes)
- Create: `templates/layouts/public.html`
- Create: `templates/invoices/invoice_public.html`
- Modify: `templates/invoices/invoice_detail.html` (add "Copy public link" button for sent+ invoices)
- Modify: `apps/orders/views.py` (add `GenerateInvoiceFromOrderView`)
- Modify: `apps/orders/urls.py` (wire generate_invoice route)
- Modify: `templates/orders/order_detail.html` (add "Generate invoice" button)
- Modify: `apps/core/management/commands/seed_demo.py` (create ~15 invoices)

### Step 6.1 — Public views

Append to `apps/invoices/views.py`:

```python
class PublicInvoiceView(DetailView):
    """Anonymous token-gated read-only invoice view."""

    model = Invoice
    slug_field = "public_token"
    slug_url_kwarg = "token"
    template_name = "invoices/invoice_public.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return Invoice.objects.public_visible().select_related("customer")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["items"] = self.object.items.all()
        return ctx


class PublicInvoicePdfView(View):
    def get(self, request, token):
        invoice = get_object_or_404(
            Invoice.objects.public_visible(), public_token=token
        )
        pdf = render_invoice_pdf(invoice, request=request)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{invoice.number}.pdf"'
        )
        return response
```

### Step 6.2 — Wire public URLs

Append to `apps/invoices/urls.py`:

```python
path("public/<uuid:token>/", views.PublicInvoiceView.as_view(), name="public"),
path("public/<uuid:token>/pdf/", views.PublicInvoicePdfView.as_view(), name="public_pdf"),
```

### Step 6.3 — Public layout

`templates/layouts/public.html`:

```django
{% extends "base.html" %}
{% load static %}
{% block body %}
<div class="min-h-screen bg-background text-foreground">
  <header class="border-b border-border bg-card">
    <div class="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
      <a href="/" class="font-semibold">Apex</a>
      <span class="text-xs text-muted-foreground">Shared document</span>
    </div>
  </header>
  <main class="mx-auto max-w-4xl px-6 py-10">
    {% block content %}{% endblock %}
  </main>
  <footer class="border-t border-border py-6 text-center text-xs text-muted-foreground">
    Powered by Apex
  </footer>
</div>
{% endblock %}
```

### Step 6.4 — Public invoice template

`templates/invoices/invoice_public.html`:

```django
{% extends "layouts/public.html" %}
{% load apex %}
{% block title %}{{ invoice.number }}{% endblock %}

{% block content %}
<div class="flex items-start justify-between">
  <div>
    <h1 class="font-mono text-2xl font-semibold">{{ invoice.number }}</h1>
    <p class="mt-1 text-sm text-muted-foreground">
      Issued {{ invoice.issue_date|date:"M j, Y" }} · Due {{ invoice.due_date|date:"M j, Y" }}
    </p>
  </div>
  <a href="{% url 'invoices:public_pdf' invoice.public_token %}"
     class="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
    Download PDF
  </a>
</div>

<div class="mt-6 rounded-lg border border-border bg-card p-6">
  <p class="text-xs font-semibold uppercase text-muted-foreground">Bill to</p>
  <p class="mt-1 font-medium">{{ invoice.customer.name }}</p>
  {% if invoice.customer.company %}<p class="text-sm">{{ invoice.customer.company }}</p>{% endif %}

  <table class="mt-6 w-full text-sm">
    <thead class="border-b border-border text-left text-xs uppercase text-muted-foreground">
      <tr>
        <th class="py-2">Description</th>
        <th class="py-2 w-20 text-right">Qty</th>
        <th class="py-2 w-28 text-right">Unit price</th>
        <th class="py-2 w-28 text-right">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr class="border-b border-border/60">
        <td class="py-2">{{ item.description }}</td>
        <td class="py-2 text-right">{{ item.quantity }}</td>
        <td class="py-2 text-right">${{ item.unit_price|floatformat:2 }}</td>
        <td class="py-2 text-right">${{ item.amount|floatformat:2 }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="mt-6 ml-auto w-full max-w-sm">
    {% include "invoices/_invoice_totals.html" %}
  </div>
</div>
{% endblock %}
```

### Step 6.5 — Copy-public-link button on staff detail

In `templates/invoices/invoice_detail.html`, add to the action bar for sent+ invoices:

```django
{% if invoice.status != "draft" %}
  <button type="button"
          x-data
          @click="navigator.clipboard.writeText('{{ request.scheme }}://{{ request.get_host }}{% url 'invoices:public' invoice.public_token %}'); $dispatch('copied')"
          class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
    Copy public link
  </button>
{% endif %}
```

### Step 6.6 — Order → Invoice bridge

Open `apps/orders/views.py`. Append:

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin, StaffRequiredMixin
from apps.orders.models import Order


class GenerateInvoiceFromOrderView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                    StaffRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        from apps.invoices.models import Invoice, InvoiceItem
        from datetime import timedelta
        from django.utils import timezone

        order = get_object_or_404(Order, pk=pk)
        with transaction.atomic():
            invoice = Invoice.objects.create(
                customer=order.customer,
                order=order,
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timedelta(days=30),
            )
            for oi in order.items.all():
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=oi.product.name if oi.product else "Item",
                    quantity=oi.quantity,
                    unit_price=oi.unit_price,
                )
        messages.success(request, f"Invoice {invoice.number} generated from order #{order.pk}.")
        return redirect(invoice.get_absolute_url())
```

> **Assumption check:** `Order.items` is the reverse relation from `OrderItem`, and `OrderItem` has `product` + `quantity` + `unit_price` fields. Verify in `apps/orders/models.py`; adjust field names if the existing schema differs.

### Step 6.7 — Wire Orders URL

Open `apps/orders/urls.py`, add:

```python
path("<int:pk>/generate-invoice/", views.GenerateInvoiceFromOrderView.as_view(),
     name="generate_invoice"),
```

### Step 6.8 — Button on Order detail

In `templates/orders/order_detail.html`, add inside the action bar (near "Edit"):

```django
<form method="post" action="{% url 'orders:generate_invoice' order.pk %}">{% csrf_token %}
  <button class="inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
    Generate invoice
  </button>
</form>
```

### Step 6.9 — Update seed_demo

Open `apps/core/management/commands/seed_demo.py`. After Customers/Orders creation, append:

```python
# Invoices
from decimal import Decimal
from datetime import timedelta
from random import choice, randint, sample
from django.utils import timezone
from apps.customers.models import Customer
from apps.invoices.tests.factories import InvoiceFactory, InvoiceItemFactory

customers = list(Customer.objects.all()[:15])
status_distribution = (
    ["draft"] * 5 +
    ["sent"] * 5 +
    ["paid"] * 3 +
    ["void"] * 2
)
today = timezone.now().date()
for i, status in enumerate(status_distribution):
    customer = customers[i % len(customers)]
    issue = today - timedelta(days=randint(1, 90))
    due = issue + timedelta(days=30)
    inv = InvoiceFactory(
        customer=customer,
        issue_date=issue,
        due_date=due,
        tax_rate=Decimal("10.00"),
        status="draft",  # start as draft so numbering works
    )
    # Add 1-4 items
    for _ in range(randint(1, 4)):
        InvoiceItemFactory(
            invoice=inv,
            quantity=randint(1, 5),
            unit_price=Decimal(str(randint(25, 500))) + Decimal("0.99"),
        )
    # Transition into target status
    if status == "sent":
        inv.mark_sent()
    elif status == "paid":
        inv.mark_sent(); inv.mark_paid()
    elif status == "void":
        inv.mark_sent(); inv.mark_void()
```

### Step 6.10 — Smoke-test seed

Run:
```bash
rm -f db.sqlite3
/Users/silkalns/.local/bin/uv run python manage.py migrate
/Users/silkalns/.local/bin/uv run python manage.py seed_demo
```
Expected: `Seeded. Demo login: demo / demo1234`, no traceback.

Verify from shell:
```bash
/Users/silkalns/.local/bin/uv run python manage.py shell -c "from apps.invoices.models import Invoice; print(Invoice.objects.count(), 'invoices:', dict((s, Invoice.objects.filter(status=s).count()) for s in ['draft','sent','paid','void']))"
```
Expected: `15 invoices: {'draft': 5, 'sent': 5, 'paid': 3, 'void': 2}`.

### Step 6.11 — Append public view tests

Append to `apps/invoices/tests/test_views.py`:

```python
# ----- Public views -----

def test_public_view_on_sent_invoice_ok(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 200
    assert inv.number.encode() in r.content


def test_public_view_on_draft_404(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 404


def test_public_view_no_auth_required(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    # No client.force_login
    r = client.get(reverse("invoices:public", args=[inv.public_token]))
    assert r.status_code == 200


def test_public_pdf_on_sent_invoice_ok(client):
    inv = InvoiceFactory(status="draft")
    InvoiceItemFactory(invoice=inv)
    inv.mark_sent()
    r = client.get(reverse("invoices:public_pdf", args=[inv.public_token]))
    assert r.status_code == 200
    assert r["Content-Type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_public_pdf_on_draft_404(client):
    inv = InvoiceFactory(status="draft")
    r = client.get(reverse("invoices:public_pdf", args=[inv.public_token]))
    assert r.status_code == 404


# ----- Order bridge -----

def test_generate_invoice_from_order(client, staff_user):
    from apps.orders.tests.factories import OrderFactory, OrderItemFactory
    client.force_login(staff_user)
    order = OrderFactory()
    OrderItemFactory(order=order, quantity=2)
    r = client.post(reverse("orders:generate_invoice", args=[order.pk]))
    assert r.status_code == 302
    inv = Invoice.objects.get()
    assert inv.order == order
    assert inv.customer == order.customer
    assert inv.items.count() == 1
```

### Step 6.12 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/invoices/tests/ apps/orders/tests/ -v 2>&1 | tail -30`
Expected: all passing. ~28 invoice tests + existing orders tests still green.

### Step 6.13 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~229 passed.

### Step 6.14 — Commit

```bash
git add apps/invoices/ apps/orders/ templates/ apps/core/management/commands/seed_demo.py
git commit -m "$(cat <<'EOF'
feat(invoices): public token-gated view + Order→Invoice bridge

UUID-token public view and PDF download route at
/invoices/public/<token>/ render under layouts/public.html (minimal
chrome, no staff dashboard). Drafts 404 on public routes.

Order detail gains "Generate invoice" button which copies line
items into a new draft invoice via
orders.GenerateInvoiceFromOrderView.

seed_demo creates 15 invoices across draft/sent/paid/void for a
realistic demo.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — E2E tests

**Files:**

- Create: `tests/e2e/test_invoices.py`

### Step 7.1 — Write Playwright tests

`tests/e2e/test_invoices.py`:

```python
"""E2E coverage for Phase 4b Invoices.

Mirrors the pattern established in tests/e2e/test_customers.py:
Playwright sync fixture, demo login, then UI-driven assertions.
"""
import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login_as_demo(page: Page, live_server):
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name='username']", "demo")
    page.fill("input[name='password']", "demo1234")
    page.click("button[type='submit']")
    expect(page).to_have_url(re.compile(r".*/$"))


def test_create_invoice_flow(page: Page, live_server):
    _login_as_demo(page, live_server)
    page.goto(f"{live_server.url}/invoices/")
    page.click("text=New invoice")
    expect(page).to_have_url(re.compile(r".*/invoices/new/$"))

    page.select_option("select[name='customer']", index=1)
    page.fill("input[name='issue_date']", "2026-06-01")
    page.fill("input[name='due_date']", "2026-06-30")
    page.fill("input[name='tax_rate']", "10")

    page.fill("input[name='items-0-description']", "Consulting hours")
    page.fill("input[name='items-0-quantity']", "4")
    page.fill("input[name='items-0-unit_price']", "150.00")

    page.click("button[type='submit']")

    # Lands on detail with computed total ($660 = 4*150*1.10)
    expect(page.locator("text=Consulting hours")).to_be_visible()
    expect(page.locator("text=$660.00")).to_be_visible()


def test_transition_lifecycle(page: Page, live_server):
    _login_as_demo(page, live_server)
    page.goto(f"{live_server.url}/invoices/")
    # Click the first draft in the list
    page.click("text=/INV-\\d{4}-\\d{4}/")

    # Send
    if page.locator("text=Send").count():
        page.click("button:has-text('Send')")
        expect(page.locator("text=marked as sent")).to_be_visible()
        expect(page.locator("text=Sent")).to_be_visible()

    # Mark paid (only on sent invoices)
    if page.locator("text=Mark paid").count():
        page.click("button:has-text('Mark paid')")
        expect(page.locator("text=marked as paid")).to_be_visible()
        expect(page.locator("text=Paid")).to_be_visible()


def test_public_view_anonymous(page: Page, live_server):
    # First login as staff, send an invoice, grab public URL
    _login_as_demo(page, live_server)
    page.goto(f"{live_server.url}/invoices/")
    page.click("text=/INV-\\d{4}-\\d{4}/")
    # Ensure it's sent
    if page.locator("button:has-text('Send')").count():
        page.click("button:has-text('Send')")
    # Copy the public link button should be visible; read the URL from its value
    public_url = page.evaluate(
        """() => {
            const btn = [...document.querySelectorAll('button')].find(
              b => b.textContent.includes('Copy public link')
            );
            if (!btn) return null;
            // Re-derive the URL from the @click binding
            const m = btn.getAttribute('@click').match(/writeText\\('([^']+)'/);
            return m ? m[1] : null;
        }"""
    )
    assert public_url is not None

    # Open in a fresh context (anonymous)
    context = page.context.browser.new_context()
    anon = context.new_page()
    anon.goto(public_url)
    expect(anon.locator("text=/INV-\\d{4}-\\d{4}/")).to_be_visible()
    expect(anon.locator("text=Download PDF")).to_be_visible()
    context.close()


def test_generate_invoice_from_order(page: Page, live_server):
    _login_as_demo(page, live_server)
    page.goto(f"{live_server.url}/orders/")
    # Click first order
    page.click("a[href*='/orders/']:not([href$='/orders/'])")
    page.click("button:has-text('Generate invoice')")
    # Lands on invoice detail
    expect(page.locator("text=/INV-\\d{4}-\\d{4}/")).to_be_visible()
```

### Step 7.2 — Run E2E tests

Start a live server is automatic via pytest-django `live_server` fixture.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_invoices.py -m e2e -v 2>&1 | tail -30`
Expected: 4 passed.

### Step 7.3 — Run full E2E suite

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: ~25 passed (21 prior + 4 new).

### Step 7.4 — Run unit suite once more for peace of mind

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ~229 passed.

### Step 7.5 — Commit

```bash
git add tests/e2e/test_invoices.py
git commit -m "$(cat <<'EOF'
test(e2e): invoice create, transitions, public view, order bridge

Four Playwright flows cover the Phase 4b happy paths: create with
line items (total computed to $660), draft→sent→paid lifecycle,
anonymous public view opens in a fresh browser context, and
order→invoice generation preserves line items.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done — Summary

- [ ] **All 7 commits landed on `phase4b-invoices` branch.**
- [ ] **~229 unit tests passing** (baseline ~180 + 49 new — covers models, forms, views, transitions, PDF, public views, order bridge).
- [ ] **~25 E2E tests passing** (baseline 21 + 4 new).
- [ ] **CHANGELOG updated** with a "Phase 4b — Invoices" entry following the Keep-A-Changelog format established by prior phases.
- [ ] **seed_demo produces 15 invoices** across realistic status distribution; `manage.py seed_demo` runs without error.
- [ ] **WeasyPrint system libs documented** in README Requirements section.
- [ ] **Sidebar shows "Invoices"** under Commerce group, staff-only.
- [ ] **Public invoice URL shareable** (e.g. `http://host/invoices/public/<uuid>/`) renders anonymously, drafts 404.

### Final verification commands

```bash
# Unit suite
/Users/silkalns/.local/bin/uv run pytest apps/ -q 2>&1 | tail -3

# E2E suite
/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3

# Smoke-test server
/Users/silkalns/.local/bin/uv run python manage.py runserver
# → visit /invoices/ as demo/demo1234, confirm list + detail + create flow + PDF download
```

### Ready-to-merge checklist

- [ ] All tests green
- [ ] No new Ruff warnings (`uv run ruff check .`)
- [ ] CHANGELOG entry written
- [ ] README Requirements updated with WeasyPrint system libs
- [ ] Squash-merge or fast-forward `phase4b-invoices` → `main`

### Next phase (Phase 4c — Notifications)

Once 4b is merged:

1. Invoice `mark_sent` / `mark_paid` hooks become natural emit points for Notification records (no code change in 4b needed; 4c wires listeners or polls).
2. The cosmetic header bell finally gets a real data source.
3. See the [parity roadmap](2026-04-24-apex-parity-roadmap.md#phase-4c--notifications) for scope.
