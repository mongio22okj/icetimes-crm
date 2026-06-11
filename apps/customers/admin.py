from django.contrib import admin

from apex.admin import ModelAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "users"
    list_display = ("name", "email", "company", "status", "created_at", "deleted_at")
    list_filter = ("status",)
    search_fields = ("name", "email", "company")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        # Admin should see everything, including archived rows.
        return Customer.all_objects.all()
