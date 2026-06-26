from django.contrib import admin

from apex.admin import ModelAdmin

from .models import IrevBroker, Lead, PushLog, TrackboxBroker


@admin.register(TrackboxBroker)
class TrackboxBrokerAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "plug"
    list_display = ("name", "base_url", "ai", "gi", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "base_url", "ai", "gi", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(IrevBroker)
class IrevBrokerAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "plug"
    list_display = ("name", "base_url", "affiliate_id", "offer_id", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "base_url", "affiliate_id", "offer_id", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "target"
    list_display = ("created_at", "full_name", "email", "phone", "country",
                    "status", "is_deposit", "broker_name")
    list_filter = ("is_deposit", "country")
    search_fields = ("firstname", "lastname", "email", "phone",
                     "click_id", "broker_lead_id")
    readonly_fields = ("click_id", "broker_lead_id", "broker_content_type",
                       "broker_object_id", "payload", "created_at", "updated_at")


@admin.register(PushLog)
class PushLogAdmin(ModelAdmin):
    apex_icon = "send"
    list_display = ("created_at", "lead", "broker_label", "success", "error")
    list_filter = ("success",)
    search_fields = ("lead__email", "lead__click_id", "error", "broker_label")
    readonly_fields = ("lead", "broker_label", "success", "response", "error", "created_at")
