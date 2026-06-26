import json
import logging
from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin, ViewerAllowedMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_ERROR, LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, TableConfig, TableView

from .forms import CampaignForm, LeadSourceForm
from .models import (
    AutoMessage,
    Campaign,
    DispatchLog,
    Lead,
    LeadSource,
    NotificationWebhook,
    SyncAudit,
)
from .services import run_sync

logger = logging.getLogger(__name__)


# ── Lead table config ────────────────────────────────────────────────────

LEADS_TABLE = TableConfig(
    key="leads",
    columns=(
        Column("id", "ID"),
        Column("firstname", "Nome"),
        Column("lastname", "Cognome"),
        Column("email", "Email"),
        Column("phone", "Telefono"),
        Column("country", "Paese"),
        Column("status", "Stato"),
        Column("source", "Broker"),
        Column("is_deposit", "FTD"),
        Column("created_at", "Data"),
    ),
    bulk_actions=(BulkAction("delete", "Elimina selezionati"),),
    default_sort="-created_at",
)


class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, ViewerAllowedMixin, TableView):
    model = Lead
    template_name = "leads/lead_list.html"
    context_object_name = "leads"
    breadcrumb_title = "Leads"
    table_config = LEADS_TABLE

    def handle_bulk_action(self, action, ids, request):
        if action.slug == "delete":
            n, _ = Lead.objects.filter(pk__in=ids).delete()
            toast(request, LEVEL_SUCCESS, f"Deleted {n} leads.")
        return redirect("leads:list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        country = (self.request.GET.get("country") or "").strip().upper()
        source = (self.request.GET.get("source") or "").strip()
        base = Lead.objects.all()
        if country:
            base = base.filter(country=country)
        if source:
            base = base.filter(source=source)
        ctx["lead_stats"] = self._period_stats(base)
        ctx["broker_options"] = [(s.slug, s.name) for s in LeadSource.objects.order_by("id")]
        ctx["current_broker"] = source
        ctx["sync_health"] = {"poller_enabled": False, "stale": True, "last_run": None}
        return ctx

    @staticmethod
    def _period_stats(base_qs=None):
        base_qs = base_qs if base_qs is not None else Lead.objects.all()
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        periods = (
            ("Ieri", today - timedelta(days=1), today - timedelta(days=1)),
            ("Oggi", today, today),
            ("Settimana", week_start, today),
            ("La settimana scorsa", last_week_start, last_week_end),
            ("Mese", month_start, today),
            ("Il mese scorso", last_month_end.replace(day=1), last_month_end),
            ("Totale", None, None),
        )
        stats = []
        for label, start, end in periods:
            qs = base_qs
            if start:
                qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)
            count = qs.count()
            deposits = qs.filter(is_deposit=True).count()
            pct = round(deposits * 100 / count, 1) if count else 0
            stats.append({"label": label, "count": count, "deposits": deposits, "pct": pct})
        return stats


class LeadSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                   StaffRequiredMixin, View):
    def post(self, request):
        result = run_sync()
        for line in result.get("ok", []):
            toast(request, LEVEL_SUCCESS, line)
        for line in result.get("errors", []):
            toast(request, LEVEL_ERROR, line)
        if not result.get("ok") and not result.get("errors"):
            toast(request, LEVEL_ERROR, "Nessuna sorgente attiva con lettura disponibile.")
        return redirect("leads:list")


# ── Broker dashboard ────────────────────────────────────────────────────

class BrokersDashboardView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           TemplateView):
    template_name = "leads/brokers_dashboard.html"
    breadcrumb_title = "Broker"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Max, Q

        ctx = super().get_context_data(**kwargs)
        sources = list(LeadSource.objects.all())
        per_source = {
            row["source"]: row for row in
            Lead.objects.values("source").annotate(
                leads=Count("id"),
                ftd=Count("id", filter=Q(is_deposit=True)),
                last=Max("created_at"),
            )
        }
        cards = []
        total_leads = total_ftd = total_revenue = 0
        for s in sources:
            matched = [
                v for k, v in per_source.items()
                if k == s.slug or k.startswith(f"{s.kind}-") or k == s.kind
            ]
            leads = sum(m["leads"] for m in matched)
            ftd = sum(m["ftd"] for m in matched)
            last = max((m["last"] for m in matched if m["last"]), default=None)
            conv = (ftd * 100 / leads) if leads else 0
            revenue = float(s.payout_per_ftd or 0) * ftd + float(s.payout_per_lead or 0) * leads
            total_leads += leads
            total_ftd += ftd
            total_revenue += revenue
            cards.append({"source": s, "leads": leads, "ftd": ftd,
                          "conv": conv, "last": last, "revenue": revenue})
        cards.sort(key=lambda c: c["revenue"], reverse=True)
        ctx["cards"] = cards
        ctx["totals"] = {
            "leads": total_leads, "ftd": total_ftd, "revenue": total_revenue,
            "conv": (total_ftd * 100 / total_leads) if total_leads else 0,
            "brokers_active": sum(1 for s in sources if s.is_active),
            "brokers_total": len(sources),
        }
        return ctx


# ── Campagne ────────────────────────────────────────────────────────────

class CampaignListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin,
                       TemplateView):
    template_name = "leads/campaign_list.html"
    breadcrumb_title = "Campagne"

    def get_context_data(self, **kwargs):
        from decimal import Decimal
        ctx = super().get_context_data(**kwargs)
        campaigns = list(Campaign.objects.all())
        ctx["campaigns"] = campaigns
        totals = {
            "budget": sum((c.budget for c in campaigns), Decimal("0")),
            "spent": sum((c.spent for c in campaigns), Decimal("0")),
            "leads": sum(c.leads_count for c in campaigns),
            "clicks": sum(c.clicks for c in campaigns),
            "active": sum(1 for c in campaigns if c.status == Campaign.STATUS_ACTIVE),
            "total": len(campaigns),
        }
        totals["cpa"] = (totals["spent"] / totals["leads"]) if totals["leads"] else None
        ctx["totals"] = totals
        return ctx


class CampaignCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         CreateView):
    model = Campaign
    form_class = CampaignForm
    template_name = "leads/campaign_form.html"
    success_url = reverse_lazy("leads:campaign_list")
    breadcrumb_title = "Nuova campagna"
    breadcrumb_parent = ("Campagne", "leads:campaign_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS, f"Campagna '{self.object.name}' creata.")
        return response


class CampaignUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         UpdateView):
    model = Campaign
    form_class = CampaignForm
    template_name = "leads/campaign_form.html"
    success_url = reverse_lazy("leads:campaign_list")
    breadcrumb_title = "Modifica campagna"
    breadcrumb_parent = ("Campagne", "leads:campaign_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS, f"Campagna '{self.object.name}' aggiornata.")
        return response


class CampaignDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                         StaffRequiredMixin, View):
    def post(self, request, pk):
        campaign = Campaign.objects.filter(pk=pk).first()
        if campaign is None:
            toast(request, LEVEL_ERROR, "Campagna non trovata.")
            return redirect("leads:campaign_list")
        name = campaign.name
        campaign.delete()
        toast(request, LEVEL_SUCCESS, f"Campagna '{name}' eliminata.")
        return redirect("leads:campaign_list")


# ── LeadSource CRUD ─────────────────────────────────────────────────────

class LeadSourceListView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         TemplateView):
    template_name = "leads/leadsource_list.html"
    breadcrumb_title = "Broker"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = LeadSource.objects.all()
        kind = self.request.GET.get("kind") or ""
        active = self.request.GET.get("active") or ""
        if kind:
            qs = qs.filter(kind=kind)
        if active == "yes":
            qs = qs.filter(is_active=True)
        elif active == "no":
            qs = qs.filter(is_active=False)
        ctx["sources"] = list(qs)
        ctx["kind_choices"] = LeadSource.KIND_CHOICES
        ctx["active_filter"] = active
        ctx["kind_filter"] = kind
        all_s = list(LeadSource.objects.all())
        ctx["total_sources"] = len(all_s)
        ctx["active_sources"] = sum(1 for s in all_s if s.is_active)
        return ctx


class LeadSourceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           CreateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/leadsource_form.html"
    success_url = reverse_lazy("leads:broker_list")
    breadcrumb_title = "Nuovo broker"
    breadcrumb_parent = ("Broker", "leads:broker_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS, f"Broker '{self.object.name}' creato.")
        return response


class LeadSourceUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           UpdateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/leadsource_form.html"
    success_url = reverse_lazy("leads:broker_list")
    breadcrumb_title = "Modifica broker"
    breadcrumb_parent = ("Broker", "leads:broker_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS, f"Broker '{self.object.name}' aggiornato.")
        return response


class LeadSourceDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    def post(self, request, pk):
        src = LeadSource.objects.filter(pk=pk).first()
        if src:
            name = src.name
            src.delete()
            toast(request, LEVEL_SUCCESS, f"Broker '{name}' eliminato.")
        return redirect("leads:broker_list")


class LeadSourceBulkDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    def post(self, request):
        ids = request.POST.getlist("ids")
        n, _ = LeadSource.objects.filter(pk__in=ids).delete()
        toast(request, LEVEL_SUCCESS, f"{n} broker eliminati.")
        return redirect("leads:broker_list")


# ── Report ──────────────────────────────────────────────────────────────

class ReportsView(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, ViewerAllowedMixin,
                  TemplateView):
    template_name = "leads/reports.html"
    breadcrumb_title = "Report"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Q

        ctx = super().get_context_data(**kwargs)
        today = timezone.localdate()
        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        labels = [d.strftime("%d/%m") for d in days]
        sources = list(LeadSource.objects.filter(is_active=True))
        datasets = []
        palette = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b",
                   "#ef4444", "#8b5cf6", "#ec4899", "#84cc16"]
        for i, s in enumerate(sources[:8]):
            per_day = (
                Lead.objects
                .filter(source__startswith=s.kind, is_deposit=True,
                        created_at__date__gte=days[0])
                .extra(select={"d": "DATE(created_at)"})
                .values("d").annotate(n=Count("id"))
            )
            counts_by_day = {row["d"]: row["n"] for row in per_day}
            datasets.append({
                "label": s.name,
                "data": [counts_by_day.get(d, 0) for d in days],
                "borderColor": palette[i % len(palette)],
                "backgroundColor": "transparent",
                "tension": 0.35,
            })
        campaigns = Campaign.objects.all()
        ctx["roi_chart_json"] = json.dumps({"labels": labels, "datasets": datasets})
        ctx["cpa_chart_json"] = json.dumps({
            "labels": [c.name for c in campaigns],
            "data": [float(c.cpa) if c.cpa is not None else 0 for c in campaigns],
            "platforms": [c.get_platform_display() for c in campaigns],
        })
        ctx["has_brokers"] = bool(sources)
        ctx["has_campaigns"] = campaigns.exists()
        return ctx


# ── Notifiche ────────────────────────────────────────────────────────────

class NotificationListView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           ListView):
    model = NotificationWebhook
    template_name = "leads/notification_list.html"
    context_object_name = "hooks"
    breadcrumb_title = "Notifiche"


class NotificationCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             CreateView):
    model = NotificationWebhook
    template_name = "leads/notification_form.html"
    success_url = reverse_lazy("leads:notification_list")
    breadcrumb_title = "Nuovo webhook"
    breadcrumb_parent = ("Notifiche", "leads:notification_list")

    def get_form_class(self):
        from .forms import NotificationWebhookForm
        return NotificationWebhookForm

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS, f"Webhook '{self.object.name}' creato.")
        return response


class NotificationUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             UpdateView):
    model = NotificationWebhook
    template_name = "leads/notification_form.html"
    success_url = reverse_lazy("leads:notification_list")
    breadcrumb_title = "Modifica webhook"
    breadcrumb_parent = ("Notifiche", "leads:notification_list")

    def get_form_class(self):
        from .forms import NotificationWebhookForm
        return NotificationWebhookForm


class NotificationDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    def post(self, request, pk):
        NotificationWebhook.objects.filter(pk=pk).delete()
        toast(request, LEVEL_SUCCESS, "Webhook eliminato.")
        return redirect("leads:notification_list")


class NotificationTestView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    def post(self, request, pk):
        from . import notifications as _n
        hook = NotificationWebhook.objects.filter(pk=pk).first()
        if hook is None:
            toast(request, LEVEL_ERROR, "Webhook non trovato.")
            return redirect("leads:notification_list")
        ok, info = _n.send_to_webhook(hook, "new_lead", {
            "name": "Test User", "email": "test@example.com",
            "phone": "+393331234567", "country": "IT", "source": "test", "score": 75,
        })
        if ok:
            toast(request, LEVEL_SUCCESS, f"Test inviato a '{hook.name}' — {info}")
        else:
            toast(request, LEVEL_ERROR, f"Test fallito — {info}")
        return redirect("leads:notification_list")


# ── Auto-email ───────────────────────────────────────────────────────────

class AutoMessageListView(BreadcrumbsMixin, LoginRequiredMixin,
                          EmailVerifiedRequiredMixin, StaffRequiredMixin,
                          ListView):
    model = AutoMessage
    template_name = "leads/auto_message_list.html"
    context_object_name = "messages_list"
    breadcrumb_title = "Auto-email"


class AutoMessageCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            CreateView):
    model = AutoMessage
    template_name = "leads/auto_message_form.html"
    success_url = reverse_lazy("leads:auto_message_list")
    breadcrumb_title = "Nuova auto-email"
    breadcrumb_parent = ("Auto-email", "leads:auto_message_list")

    def get_form_class(self):
        from .forms import AutoMessageForm
        return AutoMessageForm


class AutoMessageUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            UpdateView):
    model = AutoMessage
    template_name = "leads/auto_message_form.html"
    success_url = reverse_lazy("leads:auto_message_list")
    breadcrumb_title = "Modifica auto-email"
    breadcrumb_parent = ("Auto-email", "leads:auto_message_list")

    def get_form_class(self):
        from .forms import AutoMessageForm
        return AutoMessageForm


class AutoMessageDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            StaffRequiredMixin, View):
    def post(self, request, pk):
        AutoMessage.objects.filter(pk=pk).delete()
        toast(request, LEVEL_SUCCESS, "Auto-email eliminata.")
        return redirect("leads:auto_message_list")


# ── Dispatch log ─────────────────────────────────────────────────────────

class DispatchLogView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin,
                      ListView):
    model = DispatchLog
    template_name = "leads/dispatch_log.html"
    context_object_name = "logs"
    paginate_by = 50
    breadcrumb_title = "Dispatch log"

    def get_queryset(self):
        return DispatchLog.objects.select_related("lead", "source")

    def get_context_data(self, **kwargs):
        from django.db.models import Avg, Count, Q
        ctx = super().get_context_data(**kwargs)
        per_broker = (
            DispatchLog.objects.values("source_name")
            .annotate(total=Count("id"),
                      success=Count("id", filter=Q(success=True)),
                      avg_latency=Avg("latency_ms"))
            .order_by("-total")
        )
        for row in per_broker:
            row["rate"] = (row["success"] * 100 / row["total"]) if row["total"] else 0
        ctx["per_broker"] = per_broker
        return ctx
