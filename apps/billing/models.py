"""Showcase billing models — Subscription + PaymentMethod.

Designed as a starting point for Stripe / Paddle / Polar integration:
the field shapes match what a webhook payload typically writes, so the
swap-in is mostly replacing the seed data with real provider events.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    PLAN_CHOICES = [
        ("free",       "Free"),
        ("starter",    "Starter"),
        ("pro",        "Pro"),
        ("enterprise", "Enterprise"),
    ]
    STATUS_CHOICES = [
        ("trialing",  "Trialing"),
        ("active",    "Active"),
        ("past_due",  "Past due"),
        ("canceled",  "Canceled"),
    ]
    BILLING_CYCLE = [
        ("monthly", "Monthly"),
        ("annual",  "Annual"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.CharField(max_length=16, choices=PLAN_CHOICES, default="free")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")
    billing_cycle = models.CharField(max_length=8, choices=BILLING_CYCLE, default="monthly")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    currency = models.CharField(max_length=3, default="USD")
    billing_email = models.EmailField(blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    renews_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    seats = models.PositiveIntegerField(default=1)

    # Showcase usage metering — three sample meters that pair with the SaaS
    # dashboard's "limits" story. Buyers swap these for real metrics.
    usage_seats = models.PositiveIntegerField(default=0)
    usage_storage_gb = models.PositiveIntegerField(default=0)
    usage_api_calls = models.PositiveIntegerField(default=0)

    PLAN_LIMITS = {
        "free":       {"seats": 1,   "storage_gb": 1,    "api_calls": 1000},
        "starter":    {"seats": 5,   "storage_gb": 10,   "api_calls": 25000},
        "pro":        {"seats": 25,  "storage_gb": 100,  "api_calls": 250000},
        "enterprise": {"seats": 999, "storage_gb": 1000, "api_calls": 9999999},
    }

    PLAN_PRICING = {
        # (monthly, annual-per-month)
        "free":       (Decimal("0"),  Decimal("0")),
        "starter":    (Decimal("19"), Decimal("15")),
        "pro":        (Decimal("49"), Decimal("39")),
        "enterprise": (Decimal("199"),Decimal("159")),
    }

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.user.username} — {self.get_plan_display()} ({self.get_status_display()})"

    @property
    def is_canceled(self) -> bool:
        return self.status == "canceled"

    @property
    def limits(self) -> dict:
        return self.PLAN_LIMITS.get(self.plan, self.PLAN_LIMITS["free"])

    def usage_percent(self, kind: str) -> int:
        """0-100 percent for the given meter (seats/storage_gb/api_calls)."""
        used = getattr(self, f"usage_{kind}", 0)
        cap = self.limits.get(kind, 1)
        if not cap:
            return 0
        return min(100, round(used * 100 / cap))

    @property
    def usage_percent_seats(self) -> int:
        return self.usage_percent("seats")

    @property
    def usage_percent_storage_gb(self) -> int:
        return self.usage_percent("storage_gb")

    @property
    def usage_percent_api_calls(self) -> int:
        return self.usage_percent("api_calls")

    def cancel(self) -> None:
        if not self.canceled_at:
            self.canceled_at = timezone.now()
            self.status = "canceled"
            self.save(update_fields=["canceled_at", "status"])

    def reactivate(self) -> None:
        self.canceled_at = None
        self.status = "active"
        self.save(update_fields=["canceled_at", "status"])


class PaymentMethod(models.Model):
    BRANDS = [
        ("visa",        "Visa"),
        ("mastercard",  "Mastercard"),
        ("amex",        "American Express"),
        ("discover",    "Discover"),
        ("other",       "Other"),
    ]

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="payment_methods",
    )
    brand = models.CharField(max_length=16, choices=BRANDS, default="visa")
    last4 = models.CharField(max_length=4)
    exp_month = models.PositiveSmallIntegerField()
    exp_year = models.PositiveSmallIntegerField()
    cardholder = models.CharField(max_length=120, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self) -> str:
        return f"{self.get_brand_display()} •••• {self.last4}"

    def save(self, *args, **kwargs):
        # Only one default per subscription. If this one is being set
        # default, demote the others.
        if self.is_default:
            PaymentMethod.objects.filter(
                subscription=self.subscription, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
