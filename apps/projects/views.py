"""Project, Task, Milestone CBVs.

Tabbed detail surface: /projects/<slug>/                — Overview
                      /projects/<slug>/tasks/           — Task board
                      /projects/<slug>/team/            — Team members
                      /projects/<slug>/activity/        — Timeline
"""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    UpdateView,
)

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.projects.forms import MilestoneForm, ProjectForm, ProjectTaskForm
from apps.projects.models import Milestone, Project, ProjectTask

# ── List + filter ───────────────────────────────────────────────────────

class ProjectListView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      StaffRequiredMixin, ListView):
    model = Project
    template_name = "projects/list.html"
    context_object_name = "projects"
    paginate_by = 12
    breadcrumb_title = "Projects"

    def get_queryset(self):
        qs = Project.objects.all().select_related("customer", "owner")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        status = self.request.GET.get("status", "")
        if status:
            qs = qs.filter(status=status)
        priority = self.request.GET.get("priority", "")
        if priority:
            qs = qs.filter(priority=priority)
        return qs.annotate(
            tasks_total=Count("tasks"),
            tasks_done=Count("tasks", filter=Q(tasks__status="done")),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["status_filter"] = self.request.GET.get("status", "")
        ctx["priority_filter"] = self.request.GET.get("priority", "")
        ctx["status_choices"] = Project.STATUS
        ctx["priority_choices"] = Project.PRIORITY
        # Top-line counts for header chips
        all_projects = Project.objects.all()
        ctx["counts"] = {
            "total": all_projects.count(),
            "active": all_projects.filter(status="active").count(),
            "planning": all_projects.filter(status="planning").count(),
            "completed": all_projects.filter(status="completed").count(),
            "on_hold": all_projects.filter(status="on_hold").count(),
        }
        return ctx


# ── Detail tabs ─────────────────────────────────────────────────────────

class _ProjectTabBase(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      StaffRequiredMixin, DetailView):
    model = Project
    slug_url_kwarg = "slug"
    breadcrumb_parent = "projects:list"
    active_tab = "overview"

    def get_breadcrumb_title(self):
        return self.object.name

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = self.object
        ctx["active_tab"] = self.active_tab
        ctx["task_count"] = project.task_count
        ctx["completed_task_count"] = project.completed_task_count
        ctx["computed_progress"] = project.computed_progress
        ctx["milestones"] = project.milestones.all()
        ctx["team"] = project.team.all()
        return ctx


class ProjectOverviewView(_ProjectTabBase):
    template_name = "projects/detail_overview.html"
    active_tab = "overview"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent_tasks"] = self.object.tasks.select_related("assignee")[:6]
        ctx["milestone_form"] = MilestoneForm()
        return ctx


class ProjectTasksView(_ProjectTabBase):
    template_name = "projects/detail_tasks.html"
    active_tab = "tasks"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tasks = self.object.tasks.select_related("assignee")
        columns = []
        for key, label in ProjectTask.STATUS:
            columns.append({
                "key": key, "label": label,
                "tasks": [t for t in tasks if t.status == key],
            })
        ctx["columns"] = columns
        ctx["task_form"] = ProjectTaskForm()
        return ctx


class ProjectTeamView(_ProjectTabBase):
    template_name = "projects/detail_team.html"
    active_tab = "team"


class ProjectActivityView(_ProjectTabBase):
    template_name = "projects/detail_activity.html"
    active_tab = "activity"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Synthesize a timeline from tasks + milestones (real activity log
        # is out-of-scope for this phase — uses model timestamps directly)
        events = []
        for t in self.object.tasks.select_related("assignee"):
            events.append({
                "kind": "task_created",
                "title": f"Task created: {t.title}",
                "when": t.created_at,
                "icon": "plus",
                "by": t.assignee,
            })
            if t.status == "done":
                events.append({
                    "kind": "task_done",
                    "title": f"Task completed: {t.title}",
                    "when": t.updated_at,
                    "icon": "check",
                    "by": t.assignee,
                })
        for m in self.object.milestones.all():
            if m.completed_at:
                events.append({
                    "kind": "milestone_done",
                    "title": f"Milestone reached: {m.title}",
                    "when": m.completed_at,
                    "icon": "trophy",
                    "by": None,
                })
        events.sort(key=lambda e: e["when"], reverse=True)
        ctx["events"] = events[:30]
        return ctx


# ── CRUD ────────────────────────────────────────────────────────────────

class ProjectCreateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"
    breadcrumb_title = "New project"
    breadcrumb_parent = "projects:list"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        # Owner is automatically on the team
        self.object.team.add(self.request.user)
        messages.success(self.request, f"Project '{self.object.name}' created.")
        return response

    def get_success_url(self):
        return reverse("projects:overview", args=[self.object.slug])


class ProjectUpdateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/form.html"
    slug_url_kwarg = "slug"
    breadcrumb_parent = "projects:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.name}"

    def get_success_url(self):
        return reverse("projects:overview", args=[self.object.slug])


class ProjectArchiveView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                         StaffRequiredMixin, View):
    def post(self, request, slug):
        project = get_object_or_404(Project.all_objects, slug=slug)
        if project.archived_at:
            project.restore()
            messages.success(request, f"'{project.name}' restored.")
        else:
            project.archive()
            messages.success(request, f"'{project.name}' archived.")
        return redirect(reverse_lazy("projects:list"))


# ── Tasks ───────────────────────────────────────────────────────────────

class ProjectTaskCreateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            StaffRequiredMixin, View):
    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        form = ProjectTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            # append at end of column
            last = project.tasks.filter(status=task.status).order_by("-position").first()
            task.position = (last.position + 1) if last else 0
            task.save()
            messages.success(request, "Task added.")
        else:
            messages.error(request, "Could not create task.")
        return redirect(reverse("projects:tasks", args=[project.slug]))


class ProjectTaskToggleStatusView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                  StaffRequiredMixin, View):
    """Cycle task through statuses: todo → in_progress → review → done → todo."""
    NEXT = {"todo": "in_progress", "in_progress": "review",
            "review": "done", "done": "todo"}

    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        task = get_object_or_404(ProjectTask, pk=pk, project=project)
        task.status = self.NEXT.get(task.status, "todo")
        task.save(update_fields=["status", "updated_at"])
        return redirect(reverse("projects:tasks", args=[project.slug]))


class ProjectTaskDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            StaffRequiredMixin, View):
    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        task = get_object_or_404(ProjectTask, pk=pk, project=project)
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect(reverse("projects:tasks", args=[project.slug]))


# ── Milestones ──────────────────────────────────────────────────────────

class MilestoneCreateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                          StaffRequiredMixin, View):
    def post(self, request, slug):
        project = get_object_or_404(Project, slug=slug)
        form = MilestoneForm(request.POST)
        if form.is_valid():
            m = form.save(commit=False)
            m.project = project
            last = project.milestones.order_by("-position").first()
            m.position = (last.position + 1) if last else 0
            m.save()
            messages.success(request, "Milestone added.")
        return redirect(reverse("projects:overview", args=[project.slug]))


class MilestoneToggleView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                          StaffRequiredMixin, View):
    def post(self, request, slug, pk):
        project = get_object_or_404(Project, slug=slug)
        m = get_object_or_404(Milestone, pk=pk, project=project)
        if m.is_completed:
            m.mark_incomplete()
        else:
            m.mark_complete()
        return redirect(reverse("projects:overview", args=[project.slug]))
