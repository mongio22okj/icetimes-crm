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

from .forms import LeadSourceForm, PartnerForm
from .models import Lead, LeadSource, Partner
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
