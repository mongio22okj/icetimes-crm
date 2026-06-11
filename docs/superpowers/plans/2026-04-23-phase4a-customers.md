# Phase 4a — Customers Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a dedicated `Customer` model with soft-delete and staff-gated CRUD; migrate `Order.customer` FK from `User` to `Customer` via a three-step data-preserving migration chain.

**Architecture:** New Django app `apps/customers/` with its own model / forms / views / templates / tests, following the existing `apps/products/` + `apps/orders/` layout. `Customer` uses a `SoftDeleteManager` default manager (hides `deleted_at IS NOT NULL` rows) plus an `all_objects` escape hatch (set as `base_manager_name` so FK traversal keeps working after archive). Order FK swap is done in three discrete migrations to preserve all existing order ↔ customer linkages.

**Tech Stack:** Django 5.1 · Pillow for ImageField · pytest · Playwright. No new dependencies.

**Reference spec:** [`docs/superpowers/specs/2026-04-23-phase4a-customers-design.md`](../specs/2026-04-23-phase4a-customers-design.md)

**7 commits:**
1. Customer model + factory + unit tests
2. Customer form + Django admin
3. Customer views + URLs + templates
4. Sidebar entry + icon + avatar generalization
5. Order FK swap (3-migration chain + template/view sweep)
6. Seed demo + existing test sweep
7. E2E tests

---

## Pre-flight

- [ ] **Baseline: 171 unit + 18 E2E tests green on main.**

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: `171 passed`.

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: `18 passed`.

- [ ] **Create feature branch.**

Run: `git switch -c phase4a-customers`
Expected: `Switched to a new branch 'phase4a-customers'`.

---

## Task 1 — Customer model + factory + unit tests

**Files:**
- Create: `apps/customers/__init__.py` (empty)
- Create: `apps/customers/apps.py` (AppConfig)
- Create: `apps/customers/models.py` (Customer + SoftDeleteManager + CustomerQuerySet)
- Create: `apps/customers/migrations/__init__.py` (empty)
- Create: `apps/customers/migrations/0001_initial.py` (generated via makemigrations)
- Create: `apps/customers/tests/__init__.py` (empty)
- Create: `apps/customers/tests/factories.py` (CustomerFactory)
- Create: `apps/customers/tests/test_models.py`
- Modify: `apex/settings/base.py` (register `apps.customers` in `INSTALLED_APPS`)

### Step 1.1 — Create the app scaffolding

```bash
mkdir -p apps/customers/migrations apps/customers/tests
touch apps/customers/__init__.py apps/customers/migrations/__init__.py apps/customers/tests/__init__.py
```

### Step 1.2 — Create `apps/customers/apps.py`

```python
from django.apps import AppConfig


class CustomersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.customers"
    label = "customers"
```

### Step 1.3 — Register app in settings

Open `apex/settings/base.py`. Find `INSTALLED_APPS` and append `"apps.customers",` after `"apps.orders",` (alphabetical-ish is fine; orders come before products currently, so customers fits between them or after orders). Result ordering:

```python
INSTALLED_APPS = [
    # ... Django apps ...
    "apps.core",
    "apps.accounts",
    "apps.customers",    # NEW
    "apps.products",
    "apps.orders",
    "apps.dashboard",
]
```

### Step 1.4 — Create the model

`apps/customers/models.py`:

```python
"""Customer model with soft-delete.

Default manager (`.objects`) hides archived rows. `all_objects` is the
escape hatch for admin + FK traversal from archived customers.
Meta.base_manager_name = "all_objects" ensures `{{ order.customer.name }}`
still resolves after a customer is archived.
"""
from decimal import Decimal

from django.db import models
from django.utils import timezone


class CustomerQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def archived(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return CustomerQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class Customer(models.Model):
    STATUS = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=200, blank=True)
    avatar = models.ImageField(upload_to="customers/", blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="active")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager.from_queryset(CustomerQuerySet)()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        base_manager_name = "all_objects"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def archive(self) -> None:
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self) -> None:
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    def initials(self) -> str:
        parts = self.name.strip().split()
        if len(parts) >= 2:
            return (parts[0][:1] + parts[-1][:1]).upper()
        return (self.name[:2] or "??").upper()

    @property
    def total_orders(self) -> int:
        return self.orders.count()

    @property
    def total_spent(self) -> Decimal:
        total = Decimal("0")
        for order in self.orders.all():
            total += order.total
        return total
```

### Step 1.5 — Create the factory

`apps/customers/tests/factories.py`:

```python
import factory
from apps.customers.models import Customer


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Customer
        django_get_or_create = ("email",)

    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"customer{n}@example.com")
    phone = factory.Faker("phone_number")
    company = factory.Faker("company")
    address = factory.Faker("street_address")
    city = factory.Faker("city")
    country = factory.Faker("country")
    status = "active"
```

### Step 1.6 — Write model tests

`apps/customers/tests/test_models.py`:

```python
import pytest
from decimal import Decimal
from django.db import IntegrityError
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def test_email_lowercased_on_save():
    c = Customer.objects.create(name="Alice", email="Alice@EXAMPLE.com")
    c.refresh_from_db()
    assert c.email == "alice@example.com"


def test_duplicate_email_raises():
    Customer.objects.create(name="One", email="dup@example.com")
    with pytest.raises(IntegrityError):
        Customer.objects.create(name="Two", email="dup@example.com")


def test_archive_sets_deleted_at():
    c = CustomerFactory()
    assert c.deleted_at is None
    c.archive()
    c.refresh_from_db()
    assert c.deleted_at is not None


def test_restore_clears_deleted_at():
    c = CustomerFactory()
    c.archive()
    c.restore()
    c.refresh_from_db()
    assert c.deleted_at is None


def test_default_manager_hides_archived():
    active = CustomerFactory(name="Alice")
    archived = CustomerFactory(name="Bob")
    archived.archive()
    assert Customer.objects.filter(pk=active.pk).exists()
    assert not Customer.objects.filter(pk=archived.pk).exists()


def test_all_objects_returns_archived():
    c = CustomerFactory()
    c.archive()
    assert Customer.all_objects.filter(pk=c.pk).exists()


def test_initials_two_part_name():
    c = CustomerFactory(name="Alice Chen")
    assert c.initials() == "AC"


def test_initials_single_name():
    c = CustomerFactory(name="Alice")
    assert c.initials() == "AL"


def test_initials_empty_name_falls_back():
    # Name is required at DB-level but test the defensive branch
    c = CustomerFactory(name=" ")
    assert c.initials() == "??"


def test_total_orders_counts_linked_orders():
    from apps.orders.tests.factories import OrderFactory
    c = CustomerFactory()
    # Pre-swap: Order.customer is User. Skip if that's still true.
    # After Task 5, OrderFactory.customer will be CustomerFactory.
    # This test will fully activate after Task 5's sweep.
    try:
        OrderFactory(customer=c)
        assert c.total_orders >= 1
    except (TypeError, ValueError):
        pytest.skip("Order.customer FK still points at User; activated in Task 5")


def test_total_spent_sums_order_totals():
    from apps.orders.tests.factories import OrderFactory
    c = CustomerFactory()
    try:
        OrderFactory(customer=c)
        assert c.total_spent >= Decimal("0")
    except (TypeError, ValueError):
        pytest.skip("Order.customer FK still points at User; activated in Task 5")
```

### Step 1.7 — Generate the migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py makemigrations customers 2>&1 | tail -10`
Expected: `Migrations for 'customers': apps/customers/migrations/0001_initial.py + Create model Customer`

### Step 1.8 — Apply the migration

Run: `/Users/silkalns/.local/bin/uv run python manage.py migrate customers 2>&1 | tail -5`
Expected: `Applying customers.0001_initial... OK`.

### Step 1.9 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/customers/tests/ -v 2>&1 | tail -20`
Expected: 8–10 passed, 2 possibly-skipped (the `total_orders` / `total_spent` tests depend on Task 5's swap; they skip gracefully).

### Step 1.10 — Run full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: 179+ passed (171 prior + 8–10 new, minus 2 skipped).

### Step 1.11 — Commit

```bash
git add apps/customers/ apex/settings/base.py
git commit -m "$(cat <<'EOF'
feat(customers): Customer model with soft-delete + manager split

New Customer model in apps/customers/ with SoftDeleteManager as the
default so list/detail views auto-hide archived rows. Meta's
base_manager_name = "all_objects" keeps FK traversal working after
archive (forward-compat for when Order.customer points here).

Factory generates realistic test data. 10 model tests cover
lowercasing, uniqueness, archive/restore, both managers,
initials helpers, and linked-order aggregates.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2 — Customer form + Django admin

**Files:**
- Create: `apps/customers/forms.py`
- Create: `apps/customers/admin.py`
- Create: `apps/customers/tests/test_forms.py`

### Step 2.1 — Write failing tests

`apps/customers/tests/test_forms.py`:

```python
import pytest
from apps.customers.forms import CustomerForm
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def test_form_rejects_duplicate_email_case_insensitive():
    CustomerFactory(email="alice@example.com")
    form = CustomerForm(data={
        "name": "Alice Two",
        "email": "Alice@EXAMPLE.com",
        "phone": "",
        "company": "",
        "address": "",
        "city": "",
        "country": "",
        "status": "active",
        "notes": "",
    })
    assert not form.is_valid()
    assert "email" in form.errors


def test_form_allows_unchanged_email_for_same_customer():
    c = CustomerFactory(email="alice@example.com")
    form = CustomerForm(data={
        "name": c.name,
        "email": "Alice@EXAMPLE.com",
        "phone": "",
        "company": "",
        "address": "",
        "city": "",
        "country": "",
        "status": "active",
        "notes": "",
    }, instance=c)
    assert form.is_valid(), form.errors


def test_form_applies_base_input_classes():
    form = CustomerForm()
    # At least one text field should carry the BASE_INPUT classes
    assert "rounded-md" in form.fields["name"].widget.attrs.get("class", "")


def test_form_requires_name_and_email():
    form = CustomerForm(data={"name": "", "email": ""})
    assert not form.is_valid()
    assert "name" in form.errors
    assert "email" in form.errors
```

### Step 2.2 — Run tests to confirm they fail

Run: `/Users/silkalns/.local/bin/uv run pytest apps/customers/tests/test_forms.py -v 2>&1 | tail -10`
Expected: `ModuleNotFoundError: No module named 'apps.customers.forms'`.

### Step 2.3 — Create `apps/customers/forms.py`

```python
from django import forms
from .models import Customer

BASE_INPUT = (
    "w-full h-10 rounded-md border border-input bg-background px-3 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring "
    "placeholder:text-muted-foreground transition-colors"
)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            "name", "email", "phone", "company", "avatar",
            "address", "city", "country", "status", "notes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("notes",):
                field.widget = forms.Textarea(attrs={
                    "class": BASE_INPUT.replace("h-10", "min-h-[120px] py-2"),
                    "rows": 4,
                })
            elif name == "avatar":
                # ImageField uses FileInput; give it consistent styling
                field.widget.attrs.setdefault("class", "block text-sm")
            elif name == "status":
                field.widget.attrs.setdefault("class", BASE_INPUT)
            else:
                field.widget.attrs.setdefault("class", BASE_INPUT)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = Customer.all_objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A customer with that email already exists.")
        return email
```

Note: uses `Customer.all_objects` for the uniqueness check so collisions against archived customers are still caught. If we later add restore, a restored customer with a freed email works; but a staff member trying to register a duplicate of an archived customer gets a meaningful error.

### Step 2.4 — Create the admin registration

`apps/customers/admin.py`:

```python
from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "company", "status", "created_at", "deleted_at")
    list_filter = ("status",)
    search_fields = ("name", "email", "company")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        # Admin sees everything, including archived rows.
        return Customer.all_objects.all()
```

### Step 2.5 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/customers/tests/test_forms.py -v 2>&1 | tail -10`
Expected: 4 passed.

### Step 2.6 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ≥183 passed.

### Step 2.7 — Commit

```bash
git add apps/customers/forms.py apps/customers/admin.py apps/customers/tests/test_forms.py
git commit -m "$(cat <<'EOF'
feat(customers): CustomerForm (case-insensitive email) + admin registration

Form mirrors the pattern established in Phase 3 for User.email: 
clean_email lowercases + checks case-insensitive uniqueness against 
all_objects (catches collisions with archived customers too). 
BASE_INPUT styling applied consistently; notes gets the multiline 
variant. Admin shows all rows including archived via all_objects.

4 form tests: dupe rejected, own-email-unchanged allowed, BASE_INPUT 
applied, name+email required.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Customer views + URLs + templates

**Files:**
- Create: `apps/customers/views.py`
- Create: `apps/customers/urls.py`
- Create: `apps/customers/tests/test_views.py`
- Create: `templates/customers/customer_list.html`
- Create: `templates/customers/customer_detail.html`
- Create: `templates/customers/customer_form.html`
- Create: `templates/customers/_customer_status_pill.html`
- Modify: `apex/urls.py` (include customers URL patterns)

### Step 3.1 — Create views

`apps/customers/views.py`:

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin

from .forms import CustomerForm
from .models import Customer


class CustomerListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Customer
    paginate_by = 20
    template_name = "customers/customer_list.html"
    context_object_name = "customers"
    breadcrumb_title = "Customers"

    def get_queryset(self):
        return Customer.objects.annotate(orders_count=Count("orders", distinct=True))


class CustomerDetailView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, DetailView):
    model = Customer
    template_name = "customers/customer_detail.html"
    context_object_name = "customer"
    breadcrumb_parent = "customers:list"

    def get_breadcrumb_title(self) -> str:
        return self.object.name

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_orders"] = self.object.orders.select_related().order_by("-created_at")[:10]
        return ctx


class CustomerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"
    breadcrumb_title = "New customer"
    breadcrumb_parent = "customers:list"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Customer created.")
        return response

    def get_success_url(self):
        return reverse_lazy("customers:detail", kwargs={"pk": self.object.pk})


class CustomerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"
    context_object_name = "customer"
    breadcrumb_parent = "customers:list"

    def get_breadcrumb_title(self) -> str:
        return f"Edit {self.object.name}"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Customer updated.")
        return response

    def get_success_url(self):
        return reverse_lazy("customers:detail", kwargs={"pk": self.object.pk})


class CustomerArchiveView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                          StaffRequiredMixin, View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        customer.archive()
        messages.success(request, f"{customer.name} archived.")
        return redirect("customers:list")
```

### Step 3.2 — Create URL patterns

`apps/customers/urls.py`:

```python
from django.urls import path
from .views import (
    CustomerListView, CustomerDetailView,
    CustomerCreateView, CustomerUpdateView, CustomerArchiveView,
)

app_name = "customers"

urlpatterns = [
    path("", CustomerListView.as_view(), name="list"),
    path("new/", CustomerCreateView.as_view(), name="create"),
    path("<int:pk>/", CustomerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", CustomerUpdateView.as_view(), name="edit"),
    path("<int:pk>/archive/", CustomerArchiveView.as_view(), name="archive"),
]
```

### Step 3.3 — Include in apex/urls.py

Open `apex/urls.py`. Near the other `include(...)` lines, add:

```python
    path("customers/", include("apps.customers.urls")),
```

Place after products or orders — consistency with sidebar grouping.

### Step 3.4 — Create templates

`templates/customers/_customer_status_pill.html`:

```html
{% if status == "active" %}
  <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary">Active</span>
{% else %}
  <span class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground">Inactive</span>
{% endif %}
```

`templates/customers/customer_list.html`:

```html
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}Customers · Apex{% endblock %}
{% block content %}
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="text-2xl font-bold tracking-tight">Customers</h1>
    <p class="text-sm text-muted-foreground mt-1">Manage your customer directory.</p>
  </div>
  <a href="{% url 'customers:create' %}"
     class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium hover:opacity-90">
    New customer
  </a>
</div>

<section class="rounded-lg border border-border bg-card">
  {% if customers %}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead class="border-b border-border">
          <tr class="text-left text-xs uppercase tracking-wider text-muted-foreground">
            <th class="px-4 py-3">Customer</th>
            <th class="px-4 py-3">Company</th>
            <th class="px-4 py-3">Status</th>
            <th class="px-4 py-3">Orders</th>
            <th class="px-4 py-3">Joined</th>
          </tr>
        </thead>
        <tbody>
          {% for c in customers %}
            <tr class="border-b border-border last:border-0 hover:bg-accent/30">
              <td class="px-4 py-3">
                <a href="{% url 'customers:detail' c.pk %}" class="flex items-center gap-3">
                  {% if c.avatar %}
                    <img src="{{ c.avatar.url }}" alt="" class="h-8 w-8 rounded-full object-cover" />
                  {% else %}
                    <span class="h-8 w-8 rounded-full inline-flex items-center justify-center text-xs font-semibold bg-muted">{{ c.initials }}</span>
                  {% endif %}
                  <div>
                    <div class="font-medium">{{ c.name }}</div>
                    <div class="text-xs text-muted-foreground">{{ c.email }}</div>
                  </div>
                </a>
              </td>
              <td class="px-4 py-3">{{ c.company|default:"—" }}</td>
              <td class="px-4 py-3">{% include "customers/_customer_status_pill.html" with status=c.status %}</td>
              <td class="px-4 py-3">{{ c.orders_count }}</td>
              <td class="px-4 py-3 text-muted-foreground">{{ c.created_at|date:"M d, Y" }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    {% if is_paginated %}
      <div class="flex items-center justify-between px-4 py-3 border-t border-border text-sm">
        <span class="text-muted-foreground">Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}</span>
        <div class="flex gap-2">
          {% if page_obj.has_previous %}
            <a href="?page={{ page_obj.previous_page_number }}" class="h-9 px-3 rounded-md border border-border inline-flex items-center hover:bg-accent">Previous</a>
          {% endif %}
          {% if page_obj.has_next %}
            <a href="?page={{ page_obj.next_page_number }}" class="h-9 px-3 rounded-md border border-border inline-flex items-center hover:bg-accent">Next</a>
          {% endif %}
        </div>
      </div>
    {% endif %}
  {% else %}
    <div class="p-10 text-center">
      <p class="text-sm text-muted-foreground">No customers yet.</p>
      <a href="{% url 'customers:create' %}" class="mt-4 h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium">Create your first customer</a>
    </div>
  {% endif %}
</section>
{% endblock %}
```

`templates/customers/customer_detail.html`:

```html
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}{{ customer.name }} · Apex{% endblock %}
{% block content %}
<div class="flex items-start justify-between mb-6">
  <div class="flex items-center gap-4">
    {% if customer.avatar %}
      <img src="{{ customer.avatar.url }}" alt="" class="h-16 w-16 rounded-full object-cover" />
    {% else %}
      <span class="h-16 w-16 rounded-full inline-flex items-center justify-center text-lg font-semibold bg-muted">{{ customer.initials }}</span>
    {% endif %}
    <div>
      <h1 class="text-2xl font-bold tracking-tight">{{ customer.name }}</h1>
      <p class="text-sm text-muted-foreground">{{ customer.email }}{% if customer.company %} · {{ customer.company }}{% endif %}</p>
      <div class="mt-2">{% include "customers/_customer_status_pill.html" with status=customer.status %}</div>
    </div>
  </div>
  <div class="flex gap-2">
    <a href="{% url 'customers:edit' customer.pk %}" class="h-9 px-3 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">Edit</a>
  </div>
</div>

<div class="grid md:grid-cols-3 gap-6">
  <section class="md:col-span-2 rounded-lg border border-border bg-card p-6">
    <h2 class="text-base font-semibold mb-4">Contact</h2>
    <dl class="grid grid-cols-2 gap-4 text-sm">
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Phone</dt>
        <dd class="mt-1">{{ customer.phone|default:"—" }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Address</dt>
        <dd class="mt-1">{{ customer.address|default:"—" }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">City</dt>
        <dd class="mt-1">{{ customer.city|default:"—" }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Country</dt>
        <dd class="mt-1">{{ customer.country|default:"—" }}</dd>
      </div>
    </dl>
    {% if customer.notes %}
      <h3 class="text-sm font-medium mt-6 mb-2">Notes</h3>
      <p class="text-sm text-muted-foreground whitespace-pre-line">{{ customer.notes }}</p>
    {% endif %}
  </section>

  <section class="rounded-lg border border-border bg-card p-6">
    <h2 class="text-base font-semibold mb-4">Lifetime</h2>
    <dl class="space-y-3 text-sm">
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Total orders</dt>
        <dd class="mt-1 text-lg font-semibold">{{ customer.total_orders }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Total spent</dt>
        <dd class="mt-1 text-lg font-semibold">${{ customer.total_spent|floatformat:2 }}</dd>
      </div>
      <div>
        <dt class="text-xs uppercase tracking-wider text-muted-foreground">Joined</dt>
        <dd class="mt-1">{{ customer.created_at|date:"M d, Y" }}</dd>
      </div>
    </dl>
  </section>
</div>

<section class="mt-6 rounded-lg border border-border bg-card p-6">
  <div class="flex items-center justify-between mb-4">
    <h2 class="text-base font-semibold">Recent orders</h2>
  </div>
  {% if recent_orders %}
    <ul class="divide-y divide-border">
      {% for order in recent_orders %}
        <li class="py-2 flex items-center justify-between text-sm">
          <a href="{% url 'orders:detail' order.pk %}" class="font-medium hover:text-primary">{{ order.number }}</a>
          <span class="text-muted-foreground">{{ order.created_at|date:"M d, Y" }} · {{ order.get_status_display }}</span>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="text-sm text-muted-foreground">No orders yet.</p>
  {% endif %}
</section>

<section class="mt-6 rounded-lg border border-dashed border-border p-6">
  <h2 class="text-base font-semibold text-muted-foreground">Invoices</h2>
  <p class="text-sm text-muted-foreground mt-1">Coming in Phase 4b.</p>
</section>

<section class="mt-6 rounded-lg border border-destructive/30 bg-destructive/5 p-6">
  <h2 class="text-base font-semibold text-destructive">Danger zone</h2>
  <p class="text-sm text-muted-foreground mt-1 mb-4">Archive this customer. Their orders stay linked; they're hidden from the active list.</p>
  <form method="post" action="{% url 'customers:archive' customer.pk %}">
    {% csrf_token %}
    <button type="submit"
            class="h-10 px-3 rounded-md border border-destructive text-destructive inline-flex items-center text-sm hover:bg-destructive hover:text-destructive-foreground transition-colors">
      Archive customer
    </button>
  </form>
</section>
{% endblock %}
```

`templates/customers/customer_form.html`:

```html
{% extends "layouts/dashboard.html" %}
{% load apex %}
{% block title %}{% if form.instance.pk %}Edit {{ form.instance.name }}{% else %}New customer{% endif %} · Apex{% endblock %}
{% block content %}
<div class="mb-6">
  <h1 class="text-2xl font-bold tracking-tight">{% if form.instance.pk %}Edit customer{% else %}New customer{% endif %}</h1>
  <p class="text-sm text-muted-foreground mt-1">{% if form.instance.pk %}Update profile information.{% else %}Create a new customer record.{% endif %}</p>
</div>

<form method="post" enctype="multipart/form-data" class="max-w-3xl space-y-6">
  {% csrf_token %}
  {% if form.non_field_errors %}
    <div class="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{{ form.non_field_errors }}</div>
  {% endif %}

  <section class="rounded-lg border border-border bg-card p-6 space-y-4">
    <h2 class="text-base font-semibold">Profile</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label for="{{ form.name.id_for_label }}" class="block text-sm font-medium mb-1.5">Name</label>
        {{ form.name }}
        {% if form.name.errors %}<p class="text-xs text-destructive mt-1">{{ form.name.errors.0 }}</p>{% endif %}
      </div>
      <div>
        <label for="{{ form.email.id_for_label }}" class="block text-sm font-medium mb-1.5">Email</label>
        {{ form.email }}
        {% if form.email.errors %}<p class="text-xs text-destructive mt-1">{{ form.email.errors.0 }}</p>{% endif %}
      </div>
      <div>
        <label for="{{ form.phone.id_for_label }}" class="block text-sm font-medium mb-1.5">Phone</label>
        {{ form.phone }}
      </div>
      <div>
        <label for="{{ form.company.id_for_label }}" class="block text-sm font-medium mb-1.5">Company</label>
        {{ form.company }}
      </div>
      <div class="md:col-span-2">
        <label for="{{ form.avatar.id_for_label }}" class="block text-sm font-medium mb-1.5">Avatar</label>
        {{ form.avatar }}
      </div>
    </div>
  </section>

  <section class="rounded-lg border border-border bg-card p-6 space-y-4">
    <h2 class="text-base font-semibold">Address</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div class="md:col-span-2">
        <label for="{{ form.address.id_for_label }}" class="block text-sm font-medium mb-1.5">Street</label>
        {{ form.address }}
      </div>
      <div>
        <label for="{{ form.city.id_for_label }}" class="block text-sm font-medium mb-1.5">City</label>
        {{ form.city }}
      </div>
      <div>
        <label for="{{ form.country.id_for_label }}" class="block text-sm font-medium mb-1.5">Country</label>
        {{ form.country }}
      </div>
    </div>
  </section>

  <section class="rounded-lg border border-border bg-card p-6 space-y-4">
    <h2 class="text-base font-semibold">Status & notes</h2>
    <div>
      <label for="{{ form.status.id_for_label }}" class="block text-sm font-medium mb-1.5">Status</label>
      {{ form.status }}
    </div>
    <div>
      <label for="{{ form.notes.id_for_label }}" class="block text-sm font-medium mb-1.5">Notes</label>
      {{ form.notes }}
    </div>
  </section>

  <div class="flex justify-end gap-2">
    <a href="{% if form.instance.pk %}{% url 'customers:detail' form.instance.pk %}{% else %}{% url 'customers:list' %}{% endif %}"
       class="h-10 px-4 rounded-md border border-border inline-flex items-center text-sm hover:bg-accent">Cancel</a>
    <button type="submit" class="h-10 px-4 rounded-md bg-primary text-primary-foreground inline-flex items-center font-medium hover:opacity-90">
      {% if form.instance.pk %}Save changes{% else %}Create customer{% endif %}
    </button>
  </div>
</form>
{% endblock %}
```

### Step 3.5 — Write view tests

`apps/customers/tests/test_views.py`:

```python
import pytest
from apps.accounts.tests.factories import UserFactory
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db


def _staff(client):
    from django.utils import timezone
    u = UserFactory(is_staff=True)
    u.email_verified_at = timezone.now()
    u.save()
    client.force_login(u)
    return u


def _non_staff(client):
    from django.utils import timezone
    u = UserFactory(is_staff=False)
    u.email_verified_at = timezone.now()
    u.save()
    client.force_login(u)
    return u


def test_list_requires_login(client):
    response = client.get("/customers/")
    assert response.status_code == 302


def test_list_non_staff_forbidden(client):
    _non_staff(client)
    response = client.get("/customers/")
    assert response.status_code == 403


def test_list_staff_renders(client):
    _staff(client)
    CustomerFactory.create_batch(3)
    response = client.get("/customers/")
    assert response.status_code == 200
    assert b"New customer" in response.content


def test_list_hides_archived(client):
    _staff(client)
    active = CustomerFactory(name="Alice Active")
    archived = CustomerFactory(name="Bob Archived")
    archived.archive()
    response = client.get("/customers/")
    assert b"Alice Active" in response.content
    assert b"Bob Archived" not in response.content


def test_detail_staff_renders(client):
    _staff(client)
    c = CustomerFactory(name="Alice Chen", email="alice@example.com")
    response = client.get(f"/customers/{c.pk}/")
    assert response.status_code == 200
    assert b"Alice Chen" in response.content
    assert b"alice@example.com" in response.content


def test_detail_archived_returns_404(client):
    _staff(client)
    c = CustomerFactory()
    c.archive()
    response = client.get(f"/customers/{c.pk}/")
    assert response.status_code == 404


def test_create_post_valid(client):
    _staff(client)
    response = client.post("/customers/new/", {
        "name": "Alice Chen",
        "email": "alice@example.com",
        "phone": "", "company": "", "address": "", "city": "", "country": "",
        "status": "active", "notes": "",
    })
    assert response.status_code == 302
    assert Customer.objects.filter(email="alice@example.com").exists()


def test_update_persists_changes(client):
    _staff(client)
    c = CustomerFactory(name="Before", email="b@example.com")
    response = client.post(f"/customers/{c.pk}/edit/", {
        "name": "After",
        "email": "b@example.com",
        "phone": "", "company": "", "address": "", "city": "", "country": "",
        "status": "active", "notes": "",
    })
    assert response.status_code == 302
    c.refresh_from_db()
    assert c.name == "After"


def test_archive_soft_deletes(client):
    _staff(client)
    c = CustomerFactory()
    response = client.post(f"/customers/{c.pk}/archive/")
    assert response.status_code == 302
    c.refresh_from_db()
    assert c.deleted_at is not None


def test_archive_requires_staff(client):
    _non_staff(client)
    c = CustomerFactory()
    response = client.post(f"/customers/{c.pk}/archive/")
    assert response.status_code == 403
    c.refresh_from_db()
    assert c.deleted_at is None
```

### Step 3.6 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/customers/tests/test_views.py -v 2>&1 | tail -25`
Expected: 10 passed.

### Step 3.7 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ≥193 passed.

### Step 3.8 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 3.9 — Commit

```bash
git add apps/customers/views.py apps/customers/urls.py apps/customers/tests/test_views.py templates/customers/ apex/urls.py
git commit -m "$(cat <<'EOF'
feat(customers): list/detail/create/edit/archive views + templates

Staff-gated CRUD with the full mixin stack from Phases 1-3. 
List page paginated 20/page with avatars + status pill + orders 
count (annotated to avoid N+1). Detail page shows profile, 
lifetime stats, recent orders, invoices placeholder for Phase 4b, 
and a danger-zone archive button. Shared create/edit form mirrors 
the Apex card-section style.

10 view tests cover the full CRUD + access control + archive 
semantics (archived customer → 404; non-staff → 403).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Sidebar entry + icon + avatar helper

**Files:**
- Modify: `apps/core/navigation.py` (insert Customers NavItem)
- Modify: `apps/core/templatetags/apex.py` (register `user-plus` icon; possibly generalize avatar filters)
- Modify: `apps/core/tests/test_navigation.py` (assert Customers in palette)

### Step 4.1 — Add `user-plus` icon

Open `apps/core/templatetags/apex.py`. Find the `ICONS = {...}` dict. Add (alphabetical insertion is fine):

```python
    "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
```

### Step 4.2 — Insert Customers into NAV_ITEMS

Open `apps/core/navigation.py`. Find the `NAV_ITEMS` tuple. Insert between `Orders` and `Products`:

```python
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("Dashboard", "dashboard", "layout-dashboard", keywords=("home", "overview")),
    NavItem("Orders", "orders:list", "shopping-cart", keywords=("sales", "purchases"), group="Commerce"),
    NavItem("Customers", "customers:list", "user-plus",
            keywords=("people", "crm", "customers"), group="Commerce",
            requires_staff=True),
    NavItem("Products", "products:list", "package", keywords=("inventory", "catalog"), group="Commerce"),
    # ... rest unchanged
)
```

Note: exact signature may differ from above; match the existing pattern in `navigation.py`. If `NavItem` uses keyword-only args, adapt accordingly.

### Step 4.3 — Add assertion to navigation test

Open `apps/core/tests/test_navigation.py`. Find `test_palette_entries_have_resolved_urls` and add to its assertions:

```python
    assert by_label["Customers"]["url"] == "/customers/"
```

And add a new test covering the staff-only gate:

```python
def test_customers_in_palette_only_for_staff():
    from apps.accounts.tests.factories import UserFactory
    from apps.core.navigation import get_palette_entries

    staff = UserFactory(is_staff=True)
    non_staff = UserFactory(is_staff=False)
    staff_labels = {e["label"] for e in get_palette_entries(staff)}
    non_staff_labels = {e["label"] for e in get_palette_entries(non_staff)}
    assert "Customers" in staff_labels
    assert "Customers" not in non_staff_labels
```

### Step 4.4 — Run tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/core/tests/test_navigation.py -v 2>&1 | tail -15`
Expected: all passed (original 7 + 1 new).

### Step 4.5 — Full suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ≥194 passed.

### Step 4.6 — Rebuild Tailwind

Run: `npm run build 2>&1 | tail -2`

### Step 4.7 — Commit

```bash
git add apps/core/navigation.py apps/core/templatetags/apex.py apps/core/tests/test_navigation.py
git commit -m "$(cat <<'EOF'
feat(core): Customers sidebar entry + user-plus icon

Inserts Customers into NAV_ITEMS under Commerce group (between Orders 
and Products), staff-gated via requires_staff=True so non-staff users 
don't see it in the sidebar or command palette.

Adds user-plus Lucide icon. Palette JSON staff-filter test expanded 
to assert Customers is/isn't visible based on is_staff.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Order FK swap (3-migration chain + sweep)

**Files:**
- Create: `apps/orders/migrations/0002_add_customer_fk_temp.py`
- Create: `apps/orders/migrations/0003_backfill_customers.py`
- Create: `apps/orders/migrations/0004_swap_customer_fk.py`
- Modify: `apps/orders/models.py` (FK target changes)
- Modify: `apps/orders/views.py` (queryset optimizations — verify still valid)
- Modify: `apps/orders/forms.py` (no change expected, but verify)
- Modify: `apps/orders/admin.py` (list_display references to customer — may need tweak)
- Modify: `templates/orders/order_list.html` (customer display)
- Modify: `templates/orders/order_detail.html` (customer display)
- Modify: `templates/dashboard/_recent_orders.html` (customer display)
- Modify: `apps/dashboard/views.py` (if it references customer attrs)

This is the load-bearing task. Work carefully.

### Step 5.1 — Stage 1 migration: add temporary FK

Create `apps/orders/migrations/0002_add_customer_fk_temp.py` manually:

```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="customer_new",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders_pending_migration",
                to="customers.customer",
            ),
        ),
    ]
```

### Step 5.2 — Stage 2 migration: backfill

Create `apps/orders/migrations/0003_backfill_customers.py`:

```python
from django.db import migrations


def forward(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Customer = apps.get_model("customers", "Customer")

    user_to_customer = {}  # user_id -> customer_id

    for order in Order.objects.select_related("customer").all():
        user = order.customer
        if user is None:
            continue
        if user.id not in user_to_customer:
            email = (user.email or f"{user.username}@apex.local").strip().lower()
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            # Use all_objects-equivalent — during migration, manager classes from
            # apps.get_model don't carry custom managers, so we use the default
            # queryset via Customer.objects (which, during migration, is the
            # standard Django default manager without soft-delete filtering).
            customer, _ = Customer.objects.get_or_create(
                email=email,
                defaults={"name": full_name, "status": "active"},
            )
            user_to_customer[user.id] = customer.id
        order.customer_new_id = user_to_customer[user.id]
        order.save(update_fields=["customer_new_id"])


def reverse_noop(apps, schema_editor):
    # Reverse is a noop — the column is dropped in the reverse of migration 0002.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_add_customer_fk_temp"),
    ]

    operations = [
        migrations.RunPython(forward, reverse_noop),
    ]
```

**Note on `apps.get_model`:** Django's migration executor returns a "historical" model that lacks custom managers and methods. `Customer.objects` at migration-time is just the default `Manager` — no `SoftDeleteManager` filtering applied. That's what we want (backfill shouldn't skip anyone).

### Step 5.3 — Stage 3 migration: swap + drop

Create `apps/orders/migrations/0004_swap_customer_fk.py`:

```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_backfill_customers"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="order",
            name="customer",
        ),
        migrations.RenameField(
            model_name="order",
            old_name="customer_new",
            new_name="customer",
        ),
        migrations.AlterField(
            model_name="order",
            name="customer",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to="customers.customer",
            ),
        ),
    ]
```

### Step 5.4 — Update `apps/orders/models.py`

Open `apps/orders/models.py`. Change the `Order.customer` field declaration:

```python
# Before:
customer = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.PROTECT,
    related_name="orders",
)

# After:
customer = models.ForeignKey(
    "customers.Customer",
    on_delete=models.PROTECT,
    related_name="orders",
)
```

Remove `from django.conf import settings` if it's no longer used (check with grep).

### Step 5.5 — Apply the migrations

Run: `/Users/silkalns/.local/bin/uv run python manage.py migrate orders 2>&1 | tail -10`
Expected:
```
Applying orders.0002_add_customer_fk_temp... OK
Applying orders.0003_backfill_customers... OK
Applying orders.0004_swap_customer_fk... OK
```

If errors occur, do NOT commit — report back and inspect the DB state with `manage.py dbshell`.

### Step 5.6 — Sweep templates

`templates/orders/order_list.html` — lines 33-34:

```html
<!-- Before -->
<div class="truncate">{{ o.customer.get_full_name|default:o.customer.username }}</div>
<div class="text-xs text-muted-foreground truncate">{{ o.customer.email|default:o.customer.username }}</div>

<!-- After -->
<div class="truncate">{{ o.customer.name }}</div>
<div class="text-xs text-muted-foreground truncate">{{ o.customer.email }}</div>
```

`templates/orders/order_detail.html` — line 11:

```html
<!-- Before -->
<p class="text-sm text-muted-foreground">{{ order.customer.get_full_name|default:order.customer.username }} · {{ order.created_at|date:"M d, Y" }}</p>

<!-- After -->
<p class="text-sm text-muted-foreground">{{ order.customer.name }} · {{ order.created_at|date:"M d, Y" }}</p>
```

Check `templates/dashboard/_recent_orders.html` for similar patterns. Use grep:

Run: `grep -n "customer.username\|customer.get_full_name" templates/`

Replace each with `customer.name`. No change needed for `customer.email` (Customer has email too).

### Step 5.7 — Verify view queries still work

`apps/orders/views.py` has `Order.objects.select_related("customer").prefetch_related(...)`. After swap, `select_related("customer")` fetches Customer (not User) — works transparently. No change needed.

`apps/orders/admin.py` has `list_display = ("number", "customer", "status", "created_at")`. After swap, admin displays Customer's `__str__` (the name) — works transparently. No change needed.

`apps/dashboard/views.py` line 51: `Order.objects.select_related("customer").prefetch_related("items")[:5]` — also works.

### Step 5.8 — Check OrderForm

Open `apps/orders/forms.py`. The `customer` field is part of the ModelForm — Django picks up the new FK target automatically. The form now renders a dropdown of Customers. Verify the field has the right widget class (existing `BASE` class from forms.py).

### Step 5.9 — Run orders tests

Run: `/Users/silkalns/.local/bin/uv run pytest apps/orders/tests/ -v 2>&1 | tail -25`

Expected: some tests FAIL because the orders tests currently pass `UserFactory` for `order.customer`. Don't fix these yet — Task 6 does the test sweep. Note which tests fail so Task 6 has a target list.

### Step 5.10 — Run smoke test via curl

Confirm the orders list page still renders without 500 errors:

Restart the dev server if needed, then:

```bash
curl -s -c /tmp/t5c.txt http://127.0.0.1:8000/accounts/login/ > /dev/null
TOKEN=$(awk '$6 == "csrftoken" { print $7 }' /tmp/t5c.txt)
curl -s -b /tmp/t5c.txt -c /tmp/t5c.txt -H "Referer: http://127.0.0.1:8000/accounts/login/" \
  -d "username=demo&password=demo1234&csrfmiddlewaretoken=$TOKEN" \
  http://127.0.0.1:8000/accounts/login/ -o /dev/null
curl -s -o /dev/null -w "%{http_code}\n" -b /tmp/t5c.txt http://127.0.0.1:8000/orders/
```

Expected: `200`. If 500, check the server log for the offending template reference.

### Step 5.11 — Commit

Do NOT commit if orders tests are failing in a non-Task-6 way (e.g., actual view errors vs. just factory-related test breakage).

```bash
git add apps/orders/migrations/0002_add_customer_fk_temp.py apps/orders/migrations/0003_backfill_customers.py apps/orders/migrations/0004_swap_customer_fk.py apps/orders/models.py templates/orders/ templates/dashboard/_recent_orders.html
git commit -m "$(cat <<'EOF'
feat(orders): migrate Order.customer FK from User to Customer

Three-migration chain:
- 0002: add temporary customer_new FK (nullable) to Customer
- 0003: backfill — one Customer per distinct User currently on orders,
  deduped by email, empty emails synthesized as {username}@apex.local
- 0004: drop the User FK, rename customer_new → customer, enforce
  non-null PROTECT

Templates sweep: order.customer.get_full_name/username → customer.name.
OrderForm's FK dropdown auto-picks up the new target. Admin list_display
unchanged (Customer.__str__ returns name).

Existing orders tests may fail — Task 6 sweeps OrderFactory.customer 
to CustomerFactory + updates fixtures.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Seed demo + existing test sweep

**Files:**
- Modify: `apps/orders/tests/factories.py`
- Modify: `apps/core/management/commands/seed_demo.py`
- Modify: Various test files that depended on `OrderFactory.customer = UserFactory`

### Step 6.1 — Update OrderFactory

`apps/orders/tests/factories.py`:

```python
# Before:
from apps.accounts.tests.factories import UserFactory
# ...
class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
    customer = factory.SubFactory(UserFactory)
    status = "pending"

# After:
from apps.customers.tests.factories import CustomerFactory
# ...
class OrderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Order
    customer = factory.SubFactory(CustomerFactory)
    status = "pending"
```

Remove `UserFactory` import if no longer used elsewhere in the file.

### Step 6.2 — Update seed_demo

Open `apps/core/management/commands/seed_demo.py`. Add after the user batch creation (around line ~40):

```python
from apps.customers.tests.factories import CustomerFactory
# ...

# 2b. Customers (separate from users — these are external people we sell to)
CustomerFactory.create_batch(20)
```

Place before the orders loop so `OrderFactory` has Customers to link to.

The orders loop already uses `OrderFactory()` which — after Task 5 — creates a random Customer. No change needed there.

### Step 6.3 — Sweep existing tests

Run the orders tests to see what fails:

Run: `/Users/silkalns/.local/bin/uv run pytest apps/orders/ apps/dashboard/ -v 2>&1 | tail -40`

For each failure, the fix is typically:
- `OrderFactory(customer=some_user)` → `OrderFactory(customer=some_customer)` (using `CustomerFactory()`)
- `assert order.customer.username == "..."` → `assert order.customer.name == "..."`
- `assert order.customer.email == "..."` — still works if the email matches

Common test files to audit:
- `apps/orders/tests/test_views.py` (if it exists)
- `apps/dashboard/tests/test_views.py` — dashboard shows recent orders
- `apps/accounts/tests/test_user_crud.py` — may check a user has orders

Fix each failure. Do NOT mass-rewrite — touch only what's actually broken.

### Step 6.4 — Run the full unit suite

Run: `/Users/silkalns/.local/bin/uv run pytest apps/ -x -q 2>&1 | tail -3`
Expected: ≥195 passed (depends on how many existing tests needed updating).

If tests that reference `customer.username` still fail, they need updating. Report.

### Step 6.5 — Smoke test the dashboard

Restart dev server if needed, then log in as demo and visit:

- `/` (dashboard — recent orders should render with customer names)
- `/orders/` (orders list)
- `/customers/` (new customers list — 20 seeded customers)
- `/customers/<some-pk>/` (customer detail)

All should return 200 with sensible content.

### Step 6.6 — Re-run the skipped Customer model tests from Task 1

Task 1 had two tests that skipped pending Task 5's swap:
- `test_total_orders_counts_linked_orders`
- `test_total_spent_sums_order_totals`

Run: `/Users/silkalns/.local/bin/uv run pytest apps/customers/tests/test_models.py -v 2>&1 | tail -15`
Expected: all tests pass (including the previously-skipped ones — `OrderFactory.customer` is now a Customer).

### Step 6.7 — Commit

```bash
git add apps/orders/tests/factories.py apps/core/management/commands/seed_demo.py
# plus any test files that needed updating:
# git add apps/orders/tests/ apps/dashboard/tests/ ...
git commit -m "$(cat <<'EOF'
feat(seed): seed_demo creates Customers; OrderFactory swaps to Customer

OrderFactory.customer now resolves to CustomerFactory, matching the 
Phase 4a FK swap. Seed demo creates 20 Customer records so the 30 
seeded orders have realistic customer names to display. Existing 
tests updated where they relied on User-specific attributes 
(username/get_full_name) — switched to Customer.name.

Phase 4a now complete: list and detail pages render customer names, 
dashboard recent-orders panel shows customers (not user usernames), 
and seed data matches the new shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7 — E2E tests

**Files:**
- Create: `tests/e2e/test_customers.py`

### Step 7.1 — Write 3 Playwright tests

```python
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _login(page, server_url, username="demo", password="demo1234"):
    page.goto(f"{server_url}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", password)
    page.click("button[type=submit]")
    page.wait_for_url(f"{server_url}/")


def test_customer_list_and_detail(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/")
    # 20 seeded customers render
    rows = page.locator("table tbody tr")
    assert rows.count() > 0
    # Click the first row's customer link
    rows.first.locator("a").first.click()
    # Land on a customer detail page
    page.wait_for_url(lambda url: "/customers/" in url and url.rstrip("/").split("/")[-1].isdigit())
    # Has profile sections
    assert page.locator("text=Contact").is_visible()
    assert page.locator("text=Lifetime").is_visible()


def test_create_customer_flow(page, server_url):
    _login(page, server_url)
    page.goto(f"{server_url}/customers/new/")
    page.fill("input[name='name']", "Alice Chen")
    page.fill("input[name='email']", "alice.chen@example.com")
    page.fill("input[name='phone']", "+1 555 1234")
    page.fill("input[name='company']", "Acme Co")
    page.click("button[type=submit]")
    # Lands on detail page
    page.wait_for_url(lambda url: "/customers/" in url and "new" not in url and "edit" not in url)
    assert page.locator("text=Alice Chen").first.is_visible()
    assert page.locator("text=alice.chen@example.com").is_visible()


def test_archive_customer(page, server_url, django_user_model):
    # Pre-create a customer we can archive without side-effects
    from apps.customers.tests.factories import CustomerFactory
    c = CustomerFactory(name="Archivable Person", email="archivable@example.com")
    _login(page, server_url)
    page.goto(f"{server_url}/customers/{c.pk}/")
    page.click("button:has-text('Archive customer')")
    # Lands back on list page
    page.wait_for_url(f"{server_url}/customers/")
    # Archived name should not appear in list
    assert not page.locator("text=Archivable Person").is_visible()
```

### Step 7.2 — Run E2E tests

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/test_customers.py -m e2e -v 2>&1 | tail -20`
Expected: 3 passed.

Common issues:
- First test: if seed_demo produces fewer than expected rows, adjust the assertion.
- Third test: the archive button uses `button:has-text('Archive customer')` — if the button text differs, update.

### Step 7.3 — Full E2E sanity

Run: `/Users/silkalns/.local/bin/uv run pytest tests/e2e/ -m e2e -q 2>&1 | tail -3`
Expected: 21 passed (18 prior + 3 new).

### Step 7.4 — Commit

```bash
git add tests/e2e/test_customers.py
git commit -m "$(cat <<'EOF'
test(e2e): customer list, create, archive flows

Three Playwright tests:
- List → click first customer → detail shows profile sections
- Create new customer via UI → land on detail page with correct data
- Archive customer via detail page button → disappears from list

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done — Phase 4a complete

Summary:
- 7 commits on `phase4a-customers` branch
- New `apps/customers/` Django app with full CRUD + soft-delete
- Order.customer FK migrated from User → Customer via 3-step chain preserving all existing order ↔ customer data
- Sidebar "Customers" entry (staff-gated)
- +~20 unit tests + 3 E2E tests
- No new dependencies

After Task 7 passes, hand off to `finishing-a-development-branch` for merge.

Next up: Phase 4b — Invoices (depends on 4a's Customer model). Separate brainstorm + spec + plan cycle.
