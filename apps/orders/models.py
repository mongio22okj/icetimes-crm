"""
Order and OrderItem models.

NOTE: Order.number is generated post-save using the PK. Under concurrent inserts,
two orders could briefly have no number before the fixup runs, but the unique
constraint ensures no collisions. For production, use a database sequence or
SELECT FOR UPDATE approach instead.
"""
from decimal import Decimal

from django.db import models


class Order(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("shipped", "Shipped"),
        ("cancelled", "Cancelled"),
    ]

    number = models.CharField(max_length=20, unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or "Order(unsaved)"

    @property
    def total(self):
        return sum(
            (item.unit_price * item.quantity for item in self.items.all()),
            Decimal("0"),
        )

    def save(self, *args, **kwargs):
        is_create = self.pk is None
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"ORD-{self.pk:05d}"
            # Use queryset update to avoid recursive save() calls
            Order.objects.filter(pk=self.pk).update(number=self.number)
        if is_create:
            from apps.notifications.dispatch import notify_order_placed
            notify_order_placed(self)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product} @ {self.unit_price}"
