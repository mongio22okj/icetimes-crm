from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.tables import Column, Filter, TableConfig, TableView

from .models import ActivityEvent

ACTIVITY_TABLE = TableConfig(
    key="activity",
    columns=(
        Column("event", "Event", sortable=False, pinned=True,
               template="activity/_table_event.html"),
        Column("category", "Category",
               filter=Filter("select", choices=ActivityEvent.CATEGORY)),
        Column("actor.username", "Actor", searchable=True,
               filter=Filter("text", placeholder="Filter actor…"),
               formatter=lambda v: v or "system", priority=2),
        Column("created_at", "When", sortable=True,
               filter=Filter("daterange"), priority=2,
               formatter=lambda v: v.strftime("%b %d, %Y %H:%M") if v else ""),
    ),
    default_sort="-created_at",
    page_size=40,
    sticky_first=True,
    caption="A live timeline of what happened across your workspace.",
    empty_icon="activity",
    empty_headline="No activity yet",
    empty_body="As your team works, events will show up here.",
)


class ActivityListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, TableView):
    model = ActivityEvent
    template_name = "activity/list.html"
    context_object_name = "events"
    breadcrumb_title = "Activity"
    table_config = ACTIVITY_TABLE

    def get_queryset(self):
        qs = super().get_queryset().select_related("actor")
        # Custom "scope=mine" param — not a per-column filter, so handled here.
        if self.request.GET.get("scope") == "mine":
            qs = qs.filter(actor=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["scope"] = self.request.GET.get("scope", "")
        ctx["counts"] = ActivityEvent.objects.aggregate(
            total=Count("id"),
            today=Count("id", filter=Q(created_at__date=timezone.now().date())),
            mine=Count("id", filter=Q(actor=self.request.user)),
        )
        return ctx
