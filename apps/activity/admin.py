from django.contrib import admin

from .models import ActivityEvent


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "category", "actor", "verb", "label")
    list_filter = ("category", "verb")
    search_fields = ("label", "verb", "actor__username")
    readonly_fields = ("actor", "category", "verb", "label", "url",
                       "icon", "metadata", "created_at")
    date_hierarchy = "created_at"
