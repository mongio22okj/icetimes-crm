from django.contrib import admin

from apps.marketing.models import SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "handled", "created_at")
    list_filter = ("handled",)
    search_fields = ("subject", "email", "name")
    readonly_fields = ("created_at",)
