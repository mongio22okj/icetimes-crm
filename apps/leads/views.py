import hmac
import json
import secrets

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, FormView, ListView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_ERROR, LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from . import affinitrax, client, irev, v3
from .client import CRMAPIError
from .forms import LeadSendForm, LeadSourceForm
from .models import Lead, LeadSource
from .sources import resolve
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
               filter=Filter("text", placeholder="Filter status…")),
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


class LeadSendView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, FormView):
    """Manual lead submission towards a chosen active source."""

    template_name = "leads/lead_send.html"
    form_class = LeadSendForm
    success_url = reverse_lazy("leads:list")
    breadcrumb_title = "Send lead"
    breadcrumb_parent = "leads:list"

    def _client_ip(self):
        forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR", "")
        return (forwarded.split(",")[0].strip()
                or self.request.META.get("REMOTE_ADDR", ""))

    def form_valid(self, form):
        data = form.cleaned_data
        src = resolve(data.get("target"))
        if src is None:
            form.add_error(None, "Nessuna sorgente valida selezionata.")
            return self.form_invalid(form)
        handler = {
            LeadSource.KIND_TRACKBOX: self._send_trackbox,
            LeadSource.KIND_IREV: self._send_irev,
            LeadSource.KIND_AFFINITRAX: self._send_affinitrax,
            LeadSource.KIND_V3: self._send_v3,
        }.get(src.kind)
        if handler is None:
            form.add_error(None, f"Tipo sorgente non gestito: {src.kind}")
            return self.form_invalid(form)
        return handler(form, data, src)

    def _send_trackbox(self, form, data, src):
        account_password = secrets.token_urlsafe(10)
        affclickid = f"ice{secrets.token_hex(6)}"
        payload = {
            "firstname": data["firstname"],
            "lastname": data["lastname"],
            "email": data["email"],
            "phone": data["phone"],
            "password": account_password,
            "userip": self._client_ip(),
            "country": data["country"].upper(),
            "lg": data["lg"].upper(),
            "affclickid": affclickid,
        }
        if data.get("so"):
            payload["so"] = data["so"]
        if data.get("sub"):
            payload["sub"] = data["sub"]
        try:
            result = client.push_lead(src, payload) or {}
        except CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        self._store_local(data, uniqueid=affclickid, src=src, payload=result)
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a {src.name} (rif: {affclickid}).")
        return super().form_valid(form)

    def _send_irev(self, form, data, src):
        profile = {
            "email": data["email"],
            "phone": data["phone"],
            "first_name": data["firstname"],
            "last_name": data["lastname"],
        }
        try:
            result = irev.push_lead(src, profile, ip=self._client_ip()) or {}
        except CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        if isinstance(result, dict) and result.get("validation_errors"):
            form.add_error(None, f"IREV: {result['validation_errors']}")
            return self.form_invalid(form)
        lead_id = result.get("lead_id") if isinstance(result, dict) else None
        uniqueid = f"irev-{lead_id}" if lead_id else f"irev-man-{secrets.token_hex(5)}"
        self._store_local(data, uniqueid=uniqueid, src=src, payload=result)
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a {src.name} (rif: {lead_id or 'n/d'}).")
        return super().form_valid(form)

    def _send_affinitrax(self, form, data, src):
        click_id = f"ice{secrets.token_hex(6)}"
        payload = {
            "email": data["email"],
            "phone": data["phone"],
            "first_name": data["firstname"],
            "last_name": data["lastname"],
            "country": data["country"].upper(),
            "ip": self._client_ip(),
            "click_id": click_id,
        }
        try:
            result = affinitrax.push_lead(src, payload) or {}
        except CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        lead_id = result.get("lead_id") if isinstance(result, dict) else None
        status = (result.get("status") if isinstance(result, dict) else "") or "sent"
        self._store_local(data, uniqueid=f"afx-{lead_id}" if lead_id else click_id,
                          src=src, payload=result, status=status)
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a {src.name} (rif: {lead_id or click_id}).")
        return super().form_valid(form)

    def _send_v3(self, form, data, src):
        payload = {
            "fname": data["firstname"],
            "lname": data["lastname"],
            "email": data["email"],
            "fullphone": data["phone"],
            "ip": self._client_ip(),
            "country": data["country"].upper(),
            "language": data["lg"].lower(),
        }
        try:
            result = v3.push_lead(src, payload) or {}
        except CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        ref = ""
        if isinstance(result, dict):
            ref = str(result.get("lead_id") or result.get("id") or "")
        self._store_local(data, uniqueid=ref or f"v3-{secrets.token_hex(5)}",
                          src=src, payload=result)
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a {src.name}{f' (rif: {ref})' if ref else ''}.")
        return super().form_valid(form)

    def _store_local(self, data, *, uniqueid, src, payload, status="sent"):
        Lead.objects.create(
            uniqueid=uniqueid,
            firstname=data["firstname"],
            lastname=data["lastname"],
            email=data["email"],
            phone=data["phone"],
            country=data.get("country", "").upper(),
            status=status,
            source=src.slug,
            payload=payload if isinstance(payload, dict) else {},
        )


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


# ── Source management (Settings → API sources) ──────────────────────────

class SourceListView(BreadcrumbsMixin, LoginRequiredMixin,
                     EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = LeadSource
    template_name = "leads/source_list.html"
    context_object_name = "sources"
    breadcrumb_title = "API sources"


class SourceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin, CreateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/source_form.html"
    success_url = reverse_lazy("leads:sources")
    breadcrumb_title = "New API source"
    breadcrumb_parent = ("API sources", "leads:sources")

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
    success_url = reverse_lazy("leads:sources")
    breadcrumb_title = "Edit API source"
    breadcrumb_parent = ("API sources", "leads:sources")

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
        return redirect("leads:sources")


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
