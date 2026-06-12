import hmac
import json
import secrets

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from . import client
from .forms import LeadSendForm
from .models import Lead

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
               filter=Filter("text", placeholder="Filter status…")),
        Column("is_deposit", "Deposit", sortable=True,
               formatter=lambda v: "✓ deposit" if v else "—"),
        Column("source", "Source", priority=3),
    ),
    bulk_actions=(
        BulkAction(slug="delete", label="Delete", icon="trash", destructive=True,
                   confirm_text="Delete {n} leads? This cannot be undone."),
    ),
    exports=["csv", "xlsx"],
    page_size=25,
    default_sort="-created_at",
    sticky_first=True,
    caption="Leads ricevuti da TrackBox via postback e invii manuali.",
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


class LeadSendView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, FormView):
    """Manual lead submission form (TrackBox /api/signup/procform)."""

    template_name = "leads/lead_send.html"
    form_class = LeadSendForm
    success_url = reverse_lazy("leads:list")
    breadcrumb_title = "Send lead"
    breadcrumb_parent = "leads:list"

    def form_valid(self, form):
        # TrackBox creates an account for the lead — generate a strong
        # one-off password instead of asking the operator for one.
        account_password = secrets.token_urlsafe(10)
        # Our click id: echoed back by the {affclickid} postback macro so
        # status/deposit events update this same Lead row.
        affclickid = f"ice{secrets.token_hex(6)}"
        try:
            result = client.push_lead(
                form.to_api_payload(self.request, account_password, affclickid)
            ) or {}
        except client.CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        data = form.cleaned_data
        Lead.objects.create(
            uniqueid=affclickid,
            firstname=data["firstname"],
            lastname=data["lastname"],
            email=data["email"],
            phone=data["phone"],
            country="",
            status="sent",
            source="manual",
            payload=result if isinstance(result, dict) else {},
        )
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a TrackBox{f' (rif: {uniqueid})' if uniqueid else ''}.")
        return super().form_valid(form)


# ── Postback receiver ────────────────────────────────────────────────────
# Public endpoint TrackBox calls on lead events. Protected by a shared
# token (?token=… or X-Postback-Token header) instead of session auth —
# this is a machine-to-machine hook, not an API-key endpoint.

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

    uniqueid = str(_first(data, "uniqueid", "clickid", "uuid", "leadId",
                          "customerId", "id") or "")
    email = str(_first(data, "email") or "")
    status = str(_first(data, "callStatus", "saleStatus", "status", "statusName",
                        "event") or "")
    deposit_raw = _first(data, "isDeposit", "deposit", "ftd", "hasFTD", "type")
    event_raw = _first(data, "createdAt", "date", "time", "eventDate")
    event_at = None
    if isinstance(event_raw, str):
        event_at = parse_datetime(event_raw.replace(" ", "T"))

    lead = None
    if uniqueid:
        lead = Lead.objects.filter(uniqueid=uniqueid).order_by("-created_at").first()
    if lead is None and email:
        lead = Lead.objects.filter(email__iexact=email).order_by("-created_at").first()
    if lead is None:
        lead = Lead(source="postback")

    # Update only with non-empty incoming values so a status-only
    # postback doesn't blank out contact fields captured earlier.
    if uniqueid:
        lead.uniqueid = uniqueid
    if email:
        lead.email = email
    for field, keys in (
        ("firstname", ("firstname", "firstName", "name")),
        ("lastname", ("lastname", "lastName")),
        ("phone", ("phone", "phoneNumber")),
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
