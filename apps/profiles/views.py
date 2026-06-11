"""Public-facing profile pages.

The Settings app handles the *current user's* own preferences (password,
2FA, appearance). This app shows *other people's* profiles — name, role,
projects they're on, activity, and shared connections. Mirrors Metronic's
profile-with-tabs pattern.

Tab routes:
    /people/                       — directory
    /people/<username>/            — overview
    /people/<username>/projects/   — projects this person is on
    /people/<username>/activity/   — synthesized timeline
    /people/<username>/connections/— shared-project teammates
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.views.generic import DetailView, ListView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.projects.models import Project, ProjectTask

User = get_user_model()


class PeopleListView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                     ListView):
    model = User
    template_name = "profiles/list.html"
    context_object_name = "people"
    paginate_by = 24
    breadcrumb_title = "Team"

    def get_queryset(self):
        qs = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
                | Q(username__icontains=q) | Q(email__icontains=q)
                | Q(title__icontains=q)
            )
        role = self.request.GET.get("role", "")
        if role:
            qs = qs.filter(role=role)
        return qs.annotate(
            project_count=Count("projects", distinct=True),
            task_count=Count("project_tasks", distinct=True),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["role_filter"] = self.request.GET.get("role", "")
        ctx["role_choices"] = User.ROLE_CHOICES
        ctx["counts"] = {
            "total": User.objects.filter(is_active=True).count(),
            "admin": User.objects.filter(is_active=True, role="admin").count(),
            "manager": User.objects.filter(is_active=True, role="manager").count(),
            "staff": User.objects.filter(is_active=True, role="staff").count(),
        }
        return ctx


class _ProfileTabBase(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      DetailView):
    model = User
    slug_field = "username"
    slug_url_kwarg = "username"
    context_object_name = "person"
    breadcrumb_parent = "profiles:list"
    active_tab = "overview"

    def get_breadcrumb_title(self):
        return self.object.get_full_name() or self.object.username

    def _shared_context(self, person):
        owned = Project.objects.filter(owner=person)
        on_team = Project.objects.filter(team=person)
        all_projects = (owned | on_team).distinct()
        return {
            "active_tab": self.active_tab,
            "project_count": all_projects.count(),
            "owned_count": owned.count(),
            "task_count": ProjectTask.objects.filter(assignee=person).count(),
            "team_count": User.objects.filter(
                is_active=True, projects__in=all_projects,
            ).exclude(pk=person.pk).distinct().count(),
            "all_projects": all_projects,
        }

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(self._shared_context(self.object))
        return ctx


class ProfileOverviewView(_ProfileTabBase):
    template_name = "profiles/detail_overview.html"
    active_tab = "overview"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        person = self.object
        ctx["recent_projects"] = ctx["all_projects"].order_by("-updated_at")[:5]
        ctx["recent_tasks"] = (
            ProjectTask.objects.filter(assignee=person)
            .select_related("project").order_by("-updated_at")[:5]
        )
        return ctx


class ProfileProjectsView(_ProfileTabBase):
    template_name = "profiles/detail_projects.html"
    active_tab = "projects"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["projects"] = (
            ctx["all_projects"]
            .select_related("customer", "owner")
            .annotate(
                tasks_total=Count("tasks"),
                tasks_done=Count("tasks", filter=Q(tasks__status="done")),
            )
            .order_by("-updated_at")
        )
        return ctx


class ProfileActivityView(_ProfileTabBase):
    template_name = "profiles/detail_activity.html"
    active_tab = "activity"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        person = self.object
        events = []
        for t in ProjectTask.objects.filter(assignee=person).select_related("project"):
            events.append({
                "kind": "task_assigned", "icon": "plus",
                "title": f"Assigned to '{t.title}' in {t.project.name}",
                "url": f"/projects/{t.project.slug}/tasks/", "when": t.created_at,
            })
            if t.status == "done":
                events.append({
                    "kind": "task_done", "icon": "check",
                    "title": f"Completed '{t.title}' in {t.project.name}",
                    "url": f"/projects/{t.project.slug}/tasks/", "when": t.updated_at,
                })
        for p in Project.objects.filter(owner=person):
            events.append({
                "kind": "project_owned", "icon": "briefcase",
                "title": f"Started leading {p.name}",
                "url": f"/projects/{p.slug}/", "when": p.created_at,
            })
        events.sort(key=lambda e: e["when"], reverse=True)
        ctx["events"] = events[:30]
        return ctx


class ProfileConnectionsView(_ProfileTabBase):
    template_name = "profiles/detail_connections.html"
    active_tab = "connections"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        person = self.object
        # Materialise project IDs once so the Count(filter=Q(projects__in=...))
        # below inlines them as literals instead of nesting a subquery inside
        # the aggregate. SQL Server rejects "aggregate over a subquery"; the
        # list form is portable and at typical scales (a user's projects) is
        # also slightly faster on Postgres.
        all_project_ids = list(ctx["all_projects"].values_list("pk", flat=True))
        connections = (
            User.objects.filter(is_active=True, projects__in=all_project_ids)
            .exclude(pk=person.pk)
            .annotate(shared=Count("projects",
                                   filter=Q(projects__in=all_project_ids),
                                   distinct=True))
            .distinct()
            .order_by("-shared", "first_name")
        )
        ctx["connections"] = connections
        return ctx
