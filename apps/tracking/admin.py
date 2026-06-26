from django.contrib import admin

from apex.admin import ModelAdmin

from .models import TrackboxBroker


@admin.register(TrackboxBroker)
class TrackboxBrokerAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "plug"
    list_display = ("name", "base_url", "ai", "gi", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "base_url", "ai", "gi")
    readonly_fields = ("created_at", "updated_at")
