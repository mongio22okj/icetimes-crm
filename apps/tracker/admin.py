from django.contrib import admin
from .models import Broker, Campaign, Click

@admin.register(Broker)
class BrokerAdmin(admin.ModelAdmin):
    list_display = ["name", "offer_url", "created_at"]

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "broker", "created_at"]

@admin.register(Click)
class ClickAdmin(admin.ModelAdmin):
    list_display = ["lead_id", "campaign", "ip", "utm_source", "utm_medium", "converted", "click_time"]
    list_filter = ["converted", "utm_source", "campaign"]
    search_fields = ["lead_id", "ip", "utm_source"]
