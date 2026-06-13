"""Invoice + InvoiceItem models with state machine and auto-numbering.

State machine: draft -> sent -> (paid | void). Overdue is derived from
(status == "sent" AND due_date < today), never stored.

Invoice.number format: INV-YYYY-NNNN, per-year sequence, assigned on first
save under SELECT FOR UPDATE to serialize concurrent inserts.
"""
import uuid
from decimal import Decimal

from django.db import models, transaction
from django.db.models import F, Sum
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
        issue = self.issue_date or timezone.now().date()
        year = issue.year
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
        result = self.items.aggregate(t=Sum(F("unit_price") * F("quantity")))["t"]
        return (result if result is not None else Decimal("0")).quantize(Decimal("0.01"))

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
        from apps.notifications.dispatch import notify_invoice_sent
        notify_invoice_sent(self)
        self._dispatch_webhook("invoice.sent")

    def mark_paid(self) -> None:
        self._transition("paid", "paid_at")
        from apps.notifications.dispatch import notify_invoice_paid
        notify_invoice_paid(self)
        self._dispatch_webhook("invoice.paid")

    def mark_void(self) -> None:
        self._transition("void", "voided_at")
        from apps.notifications.dispatch import notify_invoice_void
        notify_invoice_void(self)
        self._dispatch_webhook("invoice.void")

    def transition_to(self, target: str) -> None:
        """Convenience dispatcher used by the REST API."""
        if target == "sent":
            self.mark_sent()
        elif target == "paid":
            self.mark_paid()
        elif target == "void":
            self.mark_void()
        else:
            raise InvalidTransition(f"Unknown target status: {target!r}")

    def _dispatch_webhook(self, event: str) -> None:
        """Fire a webhook for an invoice lifecycle change. Best-effort —
        delivery is logged in WebhookDelivery; failures don't bubble."""
        try:
            from apps.api.dispatch import dispatch_webhook
        except ImportError:
            return  # apps.api not installed in this project — fine.
        dispatch_webhook(event, {
            "id": self.id,
            "number": self.number,
            "customer_id": self.customer_id,
            "status": self.status,
            "total": str(self.total),
        })


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
