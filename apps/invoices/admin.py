from django.contrib import admin

from apex.admin import ModelAdmin, TabularInline
from apps.invoices.models import Invoice, InvoiceItem


class InvoiceItemInline(TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ("description", "quantity", "unit_price")


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "file-text"
    list_display = ("number", "customer", "issue_date", "due_date", "status")
    list_filter = ("status",)
    search_fields = ("number", "customer__name", "customer__email")
    readonly_fields = (
        "number", "public_token", "sent_at", "paid_at", "voided_at",
        "created_at", "updated_at",
    )
    inlines = [InvoiceItemInline]
    date_hierarchy = "issue_date"
