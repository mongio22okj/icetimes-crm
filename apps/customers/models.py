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
        name = self.name.strip()
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][:1] + parts[-1][:1]).upper()
        return (name[:2] or "??").upper()

    @property
    def total_orders(self) -> int:
        return self.orders.count()

    @property
    def total_spent(self) -> Decimal:
        total = Decimal("0")
        for order in self.orders.all():
            total += order.total
        return total
