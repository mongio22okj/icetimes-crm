from django.contrib import admin

from apex.admin import ModelAdmin

from .models import Lead, LeadSource


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "target"
    list_display = ("created_at", "firstname", "lastname", "email",
                    "phone", "country", "status", "is_deposit", "source")
    list_filter = ("is_deposit", "source", "country")
    search_fields = ("firstname", "lastname", "email", "phone", "uniqueid")
    readonly_fields = ("payload",)


@admin.register(LeadSource)
class LeadSourceAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "sliders-horizontal"
    list_display = ("name", "kind", "base_url", "is_active", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "base_url")
