from django.contrib import admin

from apex.admin import ModelAdmin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "target"
    list_display = ("created_at", "firstname", "lastname", "email",
                    "phone", "country", "status", "is_deposit", "source")
    list_filter = ("is_deposit", "source", "country")
    search_fields = ("firstname", "lastname", "email", "phone", "uniqueid")
    readonly_fields = ("payload",)
