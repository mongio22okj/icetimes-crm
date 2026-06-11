from django.contrib import admin

from .models import Milestone, Project, ProjectTask


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 1


class ProjectTaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 1
    fields = ("title", "status", "priority", "assignee", "due_date")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "priority", "progress", "owner", "customer", "due_date", "archived_at")
    list_filter = ("status", "priority")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [MilestoneInline, ProjectTaskInline]

    def get_queryset(self, request):
        return Project.all_objects.all()


@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "priority", "assignee", "due_date")
    list_filter = ("status", "priority")
    search_fields = ("title", "description")


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "due_date", "completed_at")
    list_filter = ("project",)
