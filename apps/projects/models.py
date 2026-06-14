"""Project, Milestone, and ProjectTask models.

Project supports soft delete via `archived_at`; the default manager hides
archived rows. Tasks and milestones are scoped to a project — deleting a
project cascades them.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ProjectQuerySet(models.QuerySet):
    def active(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)


class ActiveProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db).filter(archived_at__isnull=True)


class Project(models.Model):
    STATUS = [
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
    ]
    PRIORITY = [
        ("low", "Low"),
        ("med", "Medium"),
        ("high", "High"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="planning")
    priority = models.CharField(max_length=8, choices=PRIORITY, default="med")
    progress = models.PositiveIntegerField(default=0)  # 0-100

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL,
        related_name="projects", null=True, blank=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="owned_projects", null=True, blank=True,
    )
    team = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="projects", blank=True,
    )

    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveProjectManager.from_queryset(ProjectQuerySet)()
    all_objects = models.Manager()

    class Meta:
        ordering = ["-created_at"]
        base_manager_name = "all_objects"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["owner"]),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "project"
            slug = base
            i = 2
            while Project.all_objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def archive(self) -> None:
        self.archived_at = timezone.now()
        self.save(update_fields=["archived_at"])

    def restore(self) -> None:
        self.archived_at = None
        self.save(update_fields=["archived_at"])

    @property
    def task_count(self) -> int:
        return self.tasks.count()

    @property
    def completed_task_count(self) -> int:
        return self.tasks.filter(status="done").count()

    @property
    def open_task_count(self) -> int:
        return self.tasks.exclude(status="done").count()

    @property
    def computed_progress(self) -> int:
        from django.db.models import Count, Q
        counts = self.tasks.aggregate(
            total=Count("id"),
            done=Count("id", filter=Q(status="done")),
        )
        total = counts["total"] or 0
        if not total:
            return self.progress
        return round((counts["done"] or 0) * 100 / total)


class Milestone(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "due_date"]

    def __str__(self) -> str:
        return self.title

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None

    def mark_complete(self) -> None:
        if not self.completed_at:
            self.completed_at = timezone.now()
            self.save(update_fields=["completed_at"])

    def mark_incomplete(self) -> None:
        self.completed_at = None
        self.save(update_fields=["completed_at"])


class ProjectTask(models.Model):
    STATUS = [
        ("todo", "To do"),
        ("in_progress", "In Progress"),
        ("review", "Review"),
        ("done", "Done"),
    ]
    PRIORITY = [
        ("low", "Low"),
        ("med", "Medium"),
        ("high", "High"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="todo")
    priority = models.CharField(max_length=8, choices=PRIORITY, default="med")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="project_tasks", null=True, blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["status", "position", "-created_at"]

    def __str__(self) -> str:
        return self.title
