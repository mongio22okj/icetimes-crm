from django.contrib import admin

from apex.admin import ModelAdmin

from .models import LandingClick, LandingVisit, Lead, LeadSource, TrackingLink


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


@admin.register(LandingVisit)
class LandingVisitAdmin(ModelAdmin):
    list_display = ("created_at", "session_id", "page", "utm_source", "utm_campaign", "ip")
    list_filter = ("utm_source", "utm_campaign")
    search_fields = ("session_id", "page", "utm_source")
    readonly_fields = ("created_at",)


@admin.register(LandingClick)
class LandingClickAdmin(ModelAdmin):
    list_display = ("created_at", "session_id", "button_name", "page", "ip")
    search_fields = ("session_id", "button_name", "page")
    readonly_fields = ("created_at",)


@admin.register(TrackingLink)
class TrackingLinkAdmin(ModelAdmin):
    apex_icon = "link"
    list_display = ("code", "name", "source", "destination", "clicks", "is_active", "created_at")
    list_filter = ("is_active", "source")
    search_fields = ("code", "name", "destination")
    readonly_fields = ("code", "clicks", "created_at")
