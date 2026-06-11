import secrets
from datetime import datetime, time, timedelta, timezone as dt_timezone

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.generic import FormView, TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_SUCCESS, toast

from . import client
from .forms import LeadFilterForm, LeadSendForm


def _first(row, *keys):
    """Return the first non-empty value among candidate keys in an API row."""
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize(row):
    """Map a TrackBox pull row (shape not fully documented) to display fields."""
    created_raw = _first(row, "createdAt", "created_at", "signupDate", "date", "regDate")
    created_dt = None
    if isinstance(created_raw, str):
        created_dt = parse_datetime(created_raw.replace(" ", "T"))
    first = _first(row, "firstname", "firstName", "name") or ""
    last = _first(row, "lastname", "lastName") or ""
    deposit_raw = _first(row, "isDeposit", "deposit", "hasFTD", "ftd")
    return {
        "created_raw": created_raw,
        "created_dt": created_dt,
        "name": f"{first} {last}".strip() or None,
        "email": _first(row, "email"),
        "phone": _first(row, "phone", "phoneNumber"),
        "status": _first(row, "callStatus", "saleStatus", "status", "statusName"),
        "country": _first(row, "country", "countryCode", "geo"),
        "is_deposit": bool(deposit_raw) if deposit_raw is not None else None,
        "uuid": _first(row, "uuid", "id", "leadId", "customerId"),
        "raw": row,
    }


class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, TemplateView):
    """Live list of leads pulled from TrackBox.

    Data is external (not ORM), so this is a plain TemplateView with a
    filter form rather than a TableView subclass.
    """

    template_name = "leads/lead_list.html"
    breadcrumb_title = "Leads"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = LeadFilterForm(self.request.GET or None)

        today = timezone.localdate()
        date_from = today - timedelta(days=30)
        date_to = today
        pull_type = client.PULL_LEADS_AND_DEPOSITS
        if form.is_bound and form.is_valid():
            date_from = form.cleaned_data.get("date_from") or date_from
            date_to = form.cleaned_data.get("date_to") or date_to
            pull_type = form.cleaned_data.get("pull_type") or pull_type

        dt_from = datetime.combine(date_from, time.min, tzinfo=dt_timezone.utc)
        dt_to = datetime.combine(date_to, time.max, tzinfo=dt_timezone.utc)

        leads, error = [], None
        if client.is_configured():
            try:
                response = client.pull_customers(dt_from, dt_to, pull_type)
                leads = [_normalize(r) for r in client.extract_rows(response)
                         if isinstance(r, dict)]
            except client.CRMAPIError as exc:
                error = str(exc)
        else:
            error = (
                "TrackBox non configurato: impostare TRACKBOX_BASE_URL, "
                "TRACKBOX_USERNAME, TRACKBOX_PASSWORD e TRACKBOX_API_KEY "
                "nelle variabili d'ambiente del servizio."
            )

        leads.sort(key=lambda x: x.get("created_raw") or "", reverse=True)
        deposits = sum(1 for lead in leads if lead.get("is_deposit"))
        ctx.update({
            "form": form,
            "leads": leads,
            "error": error,
            "date_from": date_from,
            "date_to": date_to,
            "total": len(leads),
            "deposits": deposits,
        })
        return ctx


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
        try:
            result = client.push_lead(
                form.to_api_payload(self.request, account_password)
            ) or {}
        except client.CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        ref = ""
        if isinstance(result, dict):
            ref = result.get("uuid") or result.get("id") or ""
        toast(self.request, LEVEL_SUCCESS,
              f"Lead inviato a TrackBox{f' (rif: {ref})' if ref else ''}.")
        return super().form_valid(form)
