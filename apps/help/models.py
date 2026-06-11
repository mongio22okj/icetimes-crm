"""Help center / knowledge base models.

Two-level taxonomy: Category contains Articles. Articles store body
content as plain text with paragraph breaks (one blank line = new
paragraph). Buyers can swap to Markdown / a CMS later — the field shape
stays the same.
"""
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.CharField(max_length=300, blank=True)
    icon = models.CharField(max_length=32, default="book-open")
    accent = models.CharField(
        max_length=16, default="#16a34a",
        help_text="Hex color for the category badge background.",
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            slug = base
            i = 2
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def article_count(self) -> int:
        return self.articles.filter(is_published=True).count()


class Article(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="articles",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_featured", "-view_count", "title"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "article"
            slug = base
            i = 2
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def paragraphs(self) -> list[str]:
        """Split body on blank lines for templated paragraph rendering."""
        return [p.strip() for p in (self.body or "").split("\n\n") if p.strip()]

    @property
    def reading_minutes(self) -> int:
        words = len((self.body or "").split())
        return max(1, round(words / 200))

    def increment_views(self) -> None:
        type(self).objects.filter(pk=self.pk).update(view_count=models.F("view_count") + 1)
