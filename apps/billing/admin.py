from django.contrib import admin

from .models import PaymentMethod, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "billing_cycle", "amount", "renews_at")
    list_filter = ("plan", "status", "billing_cycle")
    search_fields = ("user__username", "user__email", "billing_email")


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("subscription", "brand", "last4", "exp_month", "exp_year", "is_default")
    list_filter = ("brand", "is_default")
