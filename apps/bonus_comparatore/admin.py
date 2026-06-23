from django.contrib import admin

from .models import Bonus, Bookmaker, ClickLog


class BonusInline(admin.TabularInline):
    model = Bonus
    extra = 0
    fields = (
        "bonus_type",
        "title",
        "amount_text",
        "is_active",
        "is_featured",
        "manual_override",
        "order",
    )
    show_change_link = True


@admin.register(Bookmaker)
class BookmakerAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "license_type",
        "rating",
        "has_affiliate",
        "is_published",
        "order",
    )
    list_filter = ("category", "license_type", "is_published")
    search_fields = ("name", "slug", "license_number")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BonusInline]
    fieldsets = (
        (None, {
            "fields": ("name", "slug", "is_published", "order"),
        }),
        ("Branding", {
            "fields": ("logo", "logo_url"),
        }),
        ("Tipologia e licenza", {
            "fields": ("category", "license_type", "license_number"),
        }),
        ("Link", {
            "fields": ("official_url", "affiliate_url"),
        }),
        ("Contenuto editoriale", {
            "fields": (
                "rating",
                "short_description",
                "full_review",
                "pros",
                "cons",
            ),
        }),
    )


@admin.register(Bonus)
class BonusAdmin(admin.ModelAdmin):
    list_display = (
        "bookmaker",
        "bonus_type",
        "title",
        "amount_text",
        "is_active",
        "is_featured",
        "manual_override",
        "last_scraped_at",
    )
    list_filter = ("bonus_type", "is_active", "is_featured", "manual_override")
    search_fields = ("title", "bookmaker__name")
    autocomplete_fields = ("bookmaker",)


@admin.register(ClickLog)
class ClickLogAdmin(admin.ModelAdmin):
    list_display = ("bookmaker", "created_at", "to_affiliate", "ip")
    list_filter = ("to_affiliate", "created_at", "bookmaker")
    search_fields = ("bookmaker__name", "ip")
    date_hierarchy = "created_at"
    readonly_fields = ("bookmaker", "created_at", "ip", "user_agent", "referer", "to_affiliate")

    def has_add_permission(self, request):
        return False  # i click si creano solo dalla view di redirect
