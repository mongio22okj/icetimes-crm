"""Public blog / articles surface.

Distinct from /help/ (internal product docs) — this is the marketing
surface for product updates, tutorials, and announcements. Posts are
authored by Users (reuses the existing accounts.User model) and tagged
with a single Category.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class Topic(models.Model):
    """Blog topic / category. One topic per post."""
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    accent = models.CharField(max_length=16, default="#16a34a")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "topic"
            slug = base
            i = 2
            while Topic.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def post_count(self) -> int:
        return self.posts.filter(is_published=True).count()


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    cover_emoji = models.CharField(max_length=8, blank=True,
        help_text="Optional emoji shown as the hero icon when no image is set.")
    topic = models.ForeignKey(
        Topic, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="posts",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="blog_posts",
    )
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(default=timezone.now)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "post"
            slug = base
            i = 2
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def paragraphs(self) -> list[str]:
        return [p.strip() for p in (self.body or "").split("\n\n") if p.strip()]

    @property
    def reading_minutes(self) -> int:
        words = len((self.body or "").split())
        return max(1, round(words / 200))

    def increment_views(self) -> None:
        type(self).objects.filter(pk=self.pk).update(
            view_count=models.F("view_count") + 1,
        )
