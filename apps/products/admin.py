from django.contrib import admin

from apex.admin import ModelAdmin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    apex_icon = "tag"
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    show_in_dashboard = True
    apex_icon = "package"
    list_display = ("name", "sku", "price", "stock", "status", "category", "created_at")
    list_filter = ("status", "category")
    search_fields = ("name", "sku", "slug")
    prepopulated_fields = {"slug": ("name",)}
