from django.contrib import admin

from apex.admin import ModelAdmin, TabularInline

from .models import Order, OrderItem


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "shopping-cart"
    list_display = ("number", "customer", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("number",)
    autocomplete_fields = ("customer",)
    inlines = [OrderItemInline]
    readonly_fields = ("number",)
