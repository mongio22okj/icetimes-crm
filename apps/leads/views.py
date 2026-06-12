import hmac
import json

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_ERROR, LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import CampaignForm, LeadSourceForm, PartnerForm
from .models import Campaign, Lead, LeadSource, Partner
from .sync import run_all_sources


LEADS_TABLE = TableConfig(
    key="leads",
    columns=(
        Column("created_at", "Received", sortable=True, pinned=True,
               filter=Filter("daterange"),
               formatter=lambda v: v.strftime("%d/%m/%Y %H:%M") if v else ""),
        Column("firstname", "First name", searchable=True),
        Column("lastname", "Last name", searchable=True),
        Column("email", "Email", searchable=True),
        Column("phone", "Phone"),
        Column("country", "Country",
               filter=Filter("text", placeholder="IT, ES…")),
        Column("status", "Status", sortable=True,
               filter=Filter("text", placeholder="Filter status…"),
               template="leads/_table_cells.html#status"),
        Column("is_deposit", "Deposit", sortable=True,
               formatter=lambda v: "✓ deposit" if v else "—"),
        Column("source", "Source", sortable=True,
               filter=Filter("text", placeholder="Filter source…")),
    ),
    bulk_actions=(
        BulkAction(slug="delete", label="Delete", icon="trash", destructive=True,
                   confirm_text="Delete {n} leads? This cannot be undone."),
    ),
    exports=["csv", "xlsx"],
    page_size=25,
    default_sort="-created_at",
    sticky_first=True,
    caption="Lead ricevuti dalle sorgenti API collegate e invii manuali.",
)


class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, TableView):
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
        ctx["lead_stats"] = self._period_stats()
        return ctx

    @staticmethod
    def _period_stats():
        """Counts + deposit conversion per period (doctorback-style panel)."""
        from datetime import timedelta

        from django.utils import timezone
        from django.utils.translation import gettext as _

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        periods = (
            (_("Today"), today, today),
            (_("Yesterday"), today - timedelta(days=1), today - timedelta(days=1)),
            (_("This week"), week_start, today),
            (_("This month"), month_start, today),
            (_("Last month"), last_month_end.replace(day=1), last_month_end),
            (_("Total"), None, None),
        )
        stats = []
        for label, start, end in periods:
            qs = Lead.objects.all()
            if start:
                qs = qs.filter(created_at__date__gte=start,
                               created_at__date__lte=end)
            count = qs.count()
            deposits = qs.filter(is_deposit=True).count()
            pct = round(deposits * 100 / count, 1) if count else 0
            stats.append({"label": label, "count": count,
                          "deposits": deposits, "pct": pct})
        return stats


class LeadSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                   StaffRequiredMixin, View):
    """Manual sync of every active, pull-capable source."""

    def post(self, request):
        ok, errors = run_all_sources()
        for line in ok:
            toast(request, LEVEL_SUCCESS, line)
        for line in errors:
            toast(request, LEVEL_ERROR, line)
        if not ok and not errors:
            toast(request, LEVEL_ERROR,
                  "Nessuna sorgente attiva con lettura disponibile.")
        return redirect("leads:list")


# ── LeadSource CRUD (manageable via direct URL or Django admin) ─────────

class SourceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, CreateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/source_form.html"
    success_url = reverse_lazy("leads:list")
    breadcrumb_title = "New API source"
    breadcrumb_parent = "leads:list"

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Sorgente '{self.object.name}' creata.")
        return response


class SourceUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, UpdateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/source_form.html"
    success_url = reverse_lazy("leads:list")
    breadcrumb_title = "Edit API source"
    breadcrumb_parent = "leads:list"

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Sorgente '{self.object.name}' aggiornata.")
        return response


class SourceDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                       StaffRequiredMixin, View):
    def post(self, request, pk):
        deleted = LeadSource.objects.filter(pk=pk).delete()[0]
        toast(request, LEVEL_SUCCESS if deleted else LEVEL_ERROR,
              "Sorgente eliminata." if deleted else "Sorgente non trovata.")
        return redirect("leads:list")


# ── API & Integrazioni page (tabs + code examples) ──────────────────────

class IntegrationsView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin,
                       TemplateView):
    template_name = "leads/integrations.html"
    breadcrumb_title = "API & Integrazioni"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        host = self.request.get_host()
        scheme = "https" if self.request.is_secure() else "http"
        ctx["default_domain"] = f"{scheme}://{host}"
        ctx["postback_token_preview"] = (
            (settings.LEADS_POSTBACK_TOKEN[:4] + "…" + settings.LEADS_POSTBACK_TOKEN[-4:])
            if getattr(settings, "LEADS_POSTBACK_TOKEN", "") else ""
        )
        return ctx


# ── Postback receiver ────────────────────────────────────────────────────
# Public endpoint external sources call on lead events. Protected by a
# shared token (?token=… or X-Postback-Token header).

def _first(data, *keys):
    for key in keys:
        value = data.get(key)
        if value not in (None, "", "null", "{", "}"):
            return value
    return None


def _truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "deposit", "ftd", "depositor"}


@csrf_exempt
def postback(request):
    expected = settings.LEADS_POSTBACK_TOKEN
    supplied = request.GET.get("token") or request.headers.get("X-Postback-Token", "")
    if not expected or not hmac.compare_digest(supplied, expected):
        return JsonResponse({"ok": False, "error": "invalid token"}, status=403)

    data = dict(request.GET.items())
    if request.method == "POST":
        if "json" in (request.content_type or ""):
            try:
                body = json.loads(request.body.decode("utf-8", errors="replace") or "{}")
                if isinstance(body, dict):
                    data.update(body)
            except json.JSONDecodeError:
                pass
        else:
            data.update(request.POST.items())
    data.pop("token", None)

    uniqueid = str(_first(data, "uniqueid", "clickid", "click_id", "uuid",
                          "leadId", "lead_id", "customerId", "id") or "")
    email = str(_first(data, "email") or "")
    status = str(_first(data, "callStatus", "saleStatus", "status", "statusName",
                        "event", "event_type") or "")
    deposit_raw = _first(data, "isDeposit", "deposit", "ftd", "hasFTD", "type",
                         "event_type")
    event_raw = _first(data, "createdAt", "date", "time", "eventDate")
    event_at = None
    if isinstance(event_raw, str):
        event_at = parse_datetime(event_raw.replace(" ", "T"))

    lead = None
    if uniqueid:
        lead = (Lead.objects.filter(uniqueid=uniqueid)
                .order_by("-created_at").first())
        if lead is None:
            # Affinitrax stores ids prefixed afx-; match those too.
            lead = (Lead.objects.filter(uniqueid=f"afx-{uniqueid}")
                    .order_by("-created_at").first())
    if lead is None and email:
        lead = Lead.objects.filter(email__iexact=email).order_by("-created_at").first()
    if lead is None:
        lead = Lead(source="postback")

    if uniqueid and not lead.uniqueid:
        lead.uniqueid = uniqueid
    if email:
        lead.email = email
    for field, keys in (
        ("firstname", ("firstname", "firstName", "first_name", "name")),
        ("lastname", ("lastname", "lastName", "last_name")),
        ("phone", ("phone", "phoneNumber", "fullphone")),
        ("country", ("country", "countryCode", "geo")),
    ):
        value = _first(data, *keys)
        if value:
            setattr(lead, field, str(value)[:120])
    if status:
        lead.status = status[:120]
    if deposit_raw is not None and _truthy(deposit_raw):
        lead.is_deposit = True
    if event_at:
        lead.event_at = event_at
    merged = dict(lead.payload or {})
    merged.update(data)
    lead.payload = merged
    lead.save()
    return JsonResponse({"ok": True, "id": lead.pk})


# ── Partner CRUD (staff-only) ───────────────────────────────────────────

class PartnerListView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Partner
    template_name = "leads/partner_list.html"
    context_object_name = "partners"
    breadcrumb_title = "Partner API"


class PartnerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        CreateView):
    model = Partner
    form_class = PartnerForm
    template_name = "leads/partner_form.html"
    success_url = reverse_lazy("leads:partner_list")
    breadcrumb_title = "Nuovo partner"
    breadcrumb_parent = ("Partner API", "leads:partner_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Partner '{self.object.name}' creato.")
        return response


class PartnerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                        EmailVerifiedRequiredMixin, StaffRequiredMixin,
                        UpdateView):
    model = Partner
    form_class = PartnerForm
    template_name = "leads/partner_form.html"
    success_url = reverse_lazy("leads:partner_list")
    breadcrumb_title = "Modifica partner"
    breadcrumb_parent = ("Partner API", "leads:partner_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Partner '{self.object.name}' aggiornato.")
        return response


class PartnerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, View):
    def post(self, request, pk):
        partner = Partner.objects.filter(pk=pk).first()
        if partner is None:
            toast(request, LEVEL_ERROR, "Partner non trovato.")
            return redirect("leads:partner_list")
        name = partner.name
        partner.delete()
        toast(request, LEVEL_SUCCESS, f"Partner '{name}' eliminato.")
        return redirect("leads:partner_list")


# ── Broker dashboard ────────────────────────────────────────────────────

class BrokersDashboardView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           TemplateView):
    """Card grid of every configured LeadSource with real-data metrics.

    For each LeadSource we compute: total leads, FTD count, conversion
    rate, last activity timestamp. Matching uses the Lead.source field
    which carries the source slug (`kind-pk` for DB rows, `kind` for env
    shims). Replaces the deleted "API Broker" page with a metrics-focused
    overview rather than a send form.
    """
    template_name = "leads/brokers_dashboard.html"
    breadcrumb_title = "Broker"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Max, Q, Sum

        ctx = super().get_context_data(**kwargs)
        sources = list(LeadSource.objects.all())

        # One pass: aggregate counts grouped by Lead.source so the page is
        # cheap even with many brokers.
        per_source = {
            row["source"]: row for row in
            Lead.objects.values("source").annotate(
                leads=Count("id"),
                ftd=Count("id", filter=Q(is_deposit=True)),
                last=Max("created_at"),
            )
        }

        cards = []
        total_leads = total_ftd = 0
        for s in sources:
            # Match leads whose Lead.source equals slug or starts with kind.
            matched = [
                v for k, v in per_source.items()
                if k == s.slug or k.startswith(f"{s.kind}-") or k == s.kind
            ]
            leads = sum(m["leads"] for m in matched)
            ftd = sum(m["ftd"] for m in matched)
            last = max((m["last"] for m in matched if m["last"]), default=None)
            conv = (ftd * 100 / leads) if leads else 0
            total_leads += leads
            total_ftd += ftd
            cards.append({
                "source": s,
                "leads": leads,
                "ftd": ftd,
                "conv": conv,
                "last": last,
            })
        cards.sort(key=lambda c: c["leads"], reverse=True)

        ctx["cards"] = cards
        ctx["totals"] = {
            "leads": total_leads,
            "ftd": total_ftd,
            "conv": (total_ftd * 100 / total_leads) if total_leads else 0,
            "brokers_active": sum(1 for s in sources if s.is_active),
            "brokers_total": len(sources),
        }
        return ctx


# ── Campaign CRUD ────────────────────────────────────────────────────────

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
        toast(self.request, LEVEL_SUCCESS,
              f"Campagna '{self.object.name}' creata.")
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
        toast(self.request, LEVEL_SUCCESS,
              f"Campagna '{self.object.name}' aggiornata.")
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


# ── Reports (ROI per broker + CPA per campaign) ─────────────────────────

class ReportsView(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin,
                  TemplateView):
    """ROI line chart per broker + CPA bar chart per campaign."""
    template_name = "leads/reports.html"
    breadcrumb_title = "Report"

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        from django.db.models import Count, Q
        from django.utils import timezone

        ctx = super().get_context_data(**kwargs)

        # ── ROI per broker: FTD count per day per broker, last 30 days ──
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
                .values("d")
                .annotate(n=Count("id"))
            )
            counts_by_day = {row["d"]: row["n"] for row in per_day}
            datasets.append({
                "label": s.name,
                "data": [counts_by_day.get(d, 0) for d in days],
                "borderColor": palette[i % len(palette)],
                "backgroundColor": "transparent",
                "tension": 0.35,
            })
        roi_chart = {"labels": labels, "datasets": datasets}

        # ── CPA per campaign: bar chart ─────────────────────────────────
        campaigns = Campaign.objects.all()
        cpa_chart = {
            "labels": [c.name for c in campaigns],
            "data": [float(c.cpa) if c.cpa is not None else 0 for c in campaigns],
            "platforms": [c.get_platform_display() for c in campaigns],
        }

        ctx["roi_chart_json"] = json.dumps(roi_chart)
        ctx["cpa_chart_json"] = json.dumps(cpa_chart)
        ctx["has_brokers"] = bool(sources)
        ctx["has_campaigns"] = campaigns.exists()
        return ctx
