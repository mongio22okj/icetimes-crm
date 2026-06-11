from django.contrib import admin

from .models import Article, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "position", "icon", "article_count")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "is_featured", "view_count", "updated_at")
    list_filter = ("category", "is_published", "is_featured")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
