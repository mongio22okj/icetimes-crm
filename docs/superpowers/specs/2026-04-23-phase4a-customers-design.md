# Phase 4a — Customers Module

**Date:** 2026-04-23
**Status:** Approved (brainstorming)
**Scope:** First of three sub-phases closing the "missing CRUD modules" gap in the 7-phase port. Introduces a dedicated `Customer` model, migrates the existing `Order.customer` FK from `User` → `Customer`, and adds full staff-gated CRUD (list / detail / create / edit / archive).

## Context

Phases 1–3 shipped the shell (palette, drawer, dropdown, breadcrumbs), the four settings tabs (profile, password, appearance, 2FA), the 2FA login challenge, and the verify-email + confirm-password auth surface. The app's foundations are solid; what's missing is content.

The reference Apex dashboard has three CRUD modules the Django port doesn't yet have: **Customers**, **Invoices**, and **Roles**. Together they're ≈17 tasks — 2× Phase 3. Decomposed into sub-phases:

- **4a — Customers** (this spec)
- **4b — Invoices** (depends on 4a because invoices link to customers)
- **4c — Roles** (independent; either Django Group surface or full ACL)

Biggest architectural tension in 4a: the current `Order.customer` FK points at `User`, mixing staff users and external customers in one table. Reference Apex separates them. Path A (migrate the FK from User → Customer) matches reference and provides a cleaner long-term foundation for 4b.

## Goals

Ship a dedicated Customers module that staff can manage end-to-end, and migrate existing Orders so they link to Customer records rather than User records.

## Non-goals

- Customer-facing login or self-service portal (customers are CRM records, not authenticated users)
- CSV import / bulk-create UI
- Duplicate-customer merging
- Customer ↔ Invoice relationship (Phase 4b)
- Restoration UI for archived customers (soft-delete is one-way in 4a; model-level `restore()` exists but no view)
- Customer messaging / notifications
- Customer self-registration from an order form

## Features

| Feature | Behaviour |
|---|---|
| **Customer CRUD** | Staff-gated list / detail / create / edit / archive. List paginated 20/page with avatar + name + email + company + status pill + orders count. Detail shows profile card + recent orders (up to 10) + total_spent (computed) + invoices placeholder. Create and edit share a form; email uniqueness enforced case-insensitively. Archive is POST-only with a second-click requirement. |
| **Soft delete** | `deleted_at` nullable timestamp. Default manager (`.objects`) hides archived rows; `all_objects` escape hatch for admin + FK traversal (via `Meta.base_manager_name = "all_objects"` so `{{ order.customer.name }}` resolves even for archived customers). |
| **Order FK migration** | Three-step migration chain swaps `Order.customer` FK target from `User` to `Customer`. Backfill creates one `Customer` per distinct User currently on orders, copying name / email. Preserves all existing order ↔ customer linkages. |
| **Sidebar nav** | New "Customers" entry under Commerce group (between Orders and Products). Staff-only via `requires_staff=True` on the `NavItem`. |
| **Seed update** | `seed_demo` creates 20 Customer records; `OrderFactory.customer` switches from `UserFactory` to `CustomerFactory`. Demo still lands on realistic data. |

## Architecture

### URLs

```
apex/urls.py
  /customers/ → include("apps.customers.urls")

apps/customers/urls.py  (app_name = "customers")
  ""                   → CustomerListView         (name="list")
  "new/"               → CustomerCreateView       (name="create")
  "<int:pk>/"          → CustomerDetailView       (name="detail")
  "<int:pk>/edit/"     → CustomerUpdateView       (name="edit")
  "<int:pk>/archive/"  → CustomerArchiveView      (name="archive")    # POST-only
```

### New app layout

```
apps/customers/
├── __init__.py
├── apps.py              CustomersConfig (default_auto_field = BigAutoField)
├── models.py            Customer + SoftDeleteManager + CustomerQuerySet
├── forms.py             CustomerForm (case-insensitive email; BASE_INPUT classes)
├── views.py             5 CBVs + standard mixin stack
├── urls.py              5 routes
├── admin.py             register Customer with list_display
├── migrations/
│   └── 0001_initial.py
└── tests/
    ├── __init__.py
    ├── factories.py     CustomerFactory
    ├── test_models.py   soft-delete, manager filter, initials, totals
    ├── test_forms.py    email uniqueness
    └── test_views.py    CRUD + archive + access control
```

### Views

All CBVs use the full mixin stack established in earlier phases:

```python
class CustomerListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Customer
    paginate_by = 20
    template_name = "customers/customer_list.html"
    context_object_name = "customers"
    breadcrumb_title = "Customers"

    def get_queryset(self):
        return Customer.objects.annotate(
            orders_count=models.Count("orders", distinct=True)
        ).order_by("-created_at")
```

The `annotate(Count("orders"))` avoids N+1 on the list page.

Similar stacks on the other four CBVs. `CustomerArchiveView` is POST-only (no GET handler) with `@method_decorator(never_cache)`.

### Templates

```
templates/customers/
├── customer_list.html           table + pagination
├── customer_detail.html         profile card + orders + invoices placeholder
├── customer_form.html           shared create/edit
└── _customer_status_pill.html   active / inactive pill (green / muted)
```

Reuses:
- `components/user_avatar.html` — generalized in this phase to accept either a `User` or a `Customer` (both have `avatar` ImageField + derivable initials).
- `partials/breadcrumbs.html` — unchanged.

### Sidebar

In `apps/core/navigation.py`, add (insert between Orders and Products in `NAV_ITEMS`):

```python
NavItem("Customers", "customers:list", "user-plus",
        keywords=("people", "crm"), group="Commerce",
        requires_staff=True),
```

Add `user-plus` icon to `apps/core/templatetags/apex.py::ICONS`.

### Dependencies

None. Pure Django + the existing template ecosystem.

## Data model

### Customer model

```python
# apps/customers/models.py
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
    STATUS = [("active", "Active"), ("inactive", "Inactive")]

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
        base_manager_name = "all_objects"  # so FK traversal works on archived rows

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def archive(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
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
    def total_spent(self):
        from decimal import Decimal
        total = Decimal("0")
        for order in self.orders.all():
            total += order.total
        return total
```

Key design notes:

- `Meta.base_manager_name = "all_objects"` resolves the "archived customer breaks FK traversal" issue — `{{ order.customer.name }}` always works, even post-archive.
- `objects` is the default manager, so list/detail views naturally exclude archived rows without explicit filtering.
- `total_spent` iterates `self.orders.all()` — fine for a single customer's detail page (small set). Avoided on the list page (we use `annotate(Count)` for counts; spent is not shown there).
- Email lowercased in `save()` — same pattern as User in Phase 3.

### Order FK migration — the load-bearing sequence

Target: `Order.customer` FK changes target from `User` → `Customer`, preserving all existing order ↔ customer linkages.

Three migrations, each individually reversible:

**Migration 1:** `apps/orders/migrations/000N_add_customer_fk_temp.py`

```python
operations = [
    migrations.AddField(
        model_name="order",
        name="customer_new",
        field=models.ForeignKey(
            "customers.Customer",
            on_delete=django.db.models.deletion.PROTECT,
            related_name="orders_pending_migration",
            null=True,
        ),
    ),
]
```

**Migration 2:** `apps/orders/migrations/000M_backfill_customers.py`

```python
def backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Customer = apps.get_model("customers", "Customer")
    user_to_customer = {}
    for order in Order.objects.select_related("customer").all():
        user = order.customer
        if user_id not in user_to_customer:
            email = (user.email or f"{user.username}@apex.local").lower()
            full_name = f"{user.first_name} {user.last_name}".strip() or user.username
            customer, _ = Customer.all_objects.get_or_create(
                email=email,
                defaults={"name": full_name, "status": "active"},
            )
            user_to_customer[user.id] = customer.id
        order.customer_new_id = user_to_customer[user.id]
        order.save(update_fields=["customer_new_id"])

def reverse_noop(apps, schema_editor):
    pass

operations = [
    migrations.RunPython(backfill, reverse_noop),
]
```

**Migration 3:** `apps/orders/migrations/000L_swap_customer_fk.py`

```python
operations = [
    migrations.RemoveField("order", "customer"),          # drops User FK
    migrations.RenameField("order", "customer_new", "customer"),
    migrations.AlterField(
        model_name="order",
        name="customer",
        field=models.ForeignKey(
            "customers.Customer",
            on_delete=django.db.models.deletion.PROTECT,
            related_name="orders",
        ),
    ),
]
```

Safety properties:
- Each migration individually reversible (Migration 1 drops the new column; Migration 2's reverse is noop — data stays but FK column goes away in Migration 1's reverse; Migration 3's reverse recreates the User FK without data, but we could backfill again).
- Backfill uses `Customer.all_objects.get_or_create` so concurrent migrations (e.g. two devs applying on different checkouts) don't produce duplicates.
- Empty email fallback (`{username}@apex.local`) mirrors the Phase 3 email-uniqueness backfill.

### OrderForm / Orders views / Orders templates

Mechanical sweep post-swap:

- `OrderForm.Meta.fields` still includes `customer`; Django auto-detects the new related model (`customers.Customer`) and renders a ModelChoiceField dropdown of Customers. No code change.
- Orders list template (`templates/orders/order_list.html`) uses `{{ order.customer.username }}` or `get_full_name|default:username`. Swap to `{{ order.customer.name }}`.
- Orders detail template (`templates/orders/order_detail.html`): same pattern.
- Orders form template (`templates/orders/order_form.html`): renders the FK dropdown — auto-generates correct options.
- Dashboard's `templates/dashboard/_recent_orders.html`: same swap.

Estimated 8–12 string replacements across 4 templates.

### Seed_demo update

`apps/core/management/commands/seed_demo.py` — add:

```python
from apps.customers.tests.factories import CustomerFactory
# ...
CustomerFactory.create_batch(20)
```

`apps/orders/tests/factories.py`:
```python
# Before:
customer = factory.SubFactory("apps.accounts.tests.factories.UserFactory")
# After:
customer = factory.SubFactory("apps.customers.tests.factories.CustomerFactory")
```

Any existing test that passed `customer=some_user` to an `OrderFactory` call needs to switch to `customer=some_customer`. Audit in commit #6.

## Error handling

- **Email collision at creation**: caught at `clean_email` with a friendly form error (matches Phase 3 pattern on User.email).
- **Email collision at update**: same, excluding `self.instance.pk`.
- **Archive of a customer with orders**: allowed. Order FK is PROTECT, so a hard-delete would fail; but `archive()` is soft. Orders still render customer name via `base_manager_name = "all_objects"`.
- **Archived customer detail access**: 404 (SoftDeleteManager filters them out of default queryset; `get_object_or_404` on the default manager raises).
- **Orphan backfill during migration**: empty-email users get `{username}@apex.local`; duplicates resolved via `get_or_create(email=..., defaults=...)`.
- **Avatar upload failure**: Django's default ImageField validation handles non-images / too-large files with form errors.

## Testing

### Unit (pytest) — ~18 new tests

**`test_customer_model.py`** (~7):
- Email lowercased on save
- DB duplicate email raises `IntegrityError`
- `archive()` sets `deleted_at`
- `restore()` clears `deleted_at`
- `Customer.objects.get(pk=archived)` raises `DoesNotExist`
- `Customer.all_objects.get(pk=archived)` returns the row
- `initials()` for two-part name, single name, empty
- `total_orders` / `total_spent` compute correctly

**`test_customer_forms.py`** (~3):
- Case-insensitive email collision rejected at form
- Update form allows unchanged email for same customer
- Form fields get BASE_INPUT classes applied

**`test_customer_views.py`** (~8):
- Unauthenticated → list redirects to login
- Authenticated non-staff → list returns 403
- Staff → list returns 200 with paginated customers
- Archived customer → detail returns 404
- Create POST valid → creates, redirects, flash present
- Update POST valid → persists change
- Archive POST → `deleted_at` set, removed from list
- Archived customer's orders still render customer name (via `base_manager_name`)

**Order-bridge regression tests** (existing tests updated, not counted as new):
- `OrderFactory.customer` now resolves to Customer
- Order detail template renders `customer.name`

### E2E (Playwright) — ~3 new tests

- Customer list → click row → detail shows correct info + orders
- Create customer flow via UI → lands on detail page
- Archive customer → confirmation → no longer in list; FK-linked order still renders the name

## Rollout — 7 commits

1. **Customer model + migration + factory** — create `apps/customers/` app, model + managers, factory, model unit tests. Register app in `INSTALLED_APPS`.
2. **Customer forms + admin** — `CustomerForm` with case-insensitive `clean_email`, register in Django admin, form tests.
3. **Customer views + URLs + templates** — list / detail / create / update / archive with full mixin stack, templates, URL namespace wired.
4. **Sidebar + icon + avatar generalization** — NAV_ITEMS entry for Customers, `user-plus` icon, `user_avatar.html` generalized to accept Customer.
5. **Order FK swap** — three-migration chain (add temp → backfill → swap + drop) plus template/form/view adjustments that reference `customer.name` instead of `customer.username`.
6. **Seed demo + existing-test sweep** — `OrderFactory.customer → CustomerFactory`, `seed_demo` creates Customers, update ~6 existing tests that expected `order.customer.username`.
7. **E2E tests** — 3 Playwright tests + verify full E2E suite still passes.

## Open questions

None. User approved all defaults and both design sections.

## Forward-compatibility notes (for Phase 4b and 4c)

- **Invoices (4b)**: Invoice will have `customer = ForeignKey("customers.Customer", on_delete=PROTECT)`. 4a's `Customer` model already has `invoices` as an unused reverse relation — 4b's FK creates it.
- **Roles (4c)**: Independent of Customers. No changes needed in 4a's code to prepare.
- **Customer self-registration**: If Phase 7 brings a public storefront, `Customer` can gain a nullable `user = OneToOneField(User, null=True)` linking a Customer record to an auth-enabled User, without breaking 4a's invariants.
