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


class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, TemplateView):
    """Live list of leads fetched from the external CRM API.

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
        is_deposit = None
        if form.is_bound and form.is_valid():
            date_from = form.cleaned_data.get("date_from") or date_from
            date_to = form.cleaned_data.get("date_to") or date_to
            deposit = form.cleaned_data.get("deposit")
            if deposit:
                is_deposit = deposit == "true"

        dt_from = datetime.combine(date_from, time.min, tzinfo=dt_timezone.utc)
        dt_to = datetime.combine(date_to, time.max, tzinfo=dt_timezone.utc)

        leads, error = [], None
        if client.is_configured():
            try:
                leads = client.get_leads(dt_from, dt_to, is_deposit)
            except client.CRMAPIError as exc:
                error = str(exc)
        else:
            error = (
                "CRM API non configurata: impostare CRM_API_BASE_URL e "
                "CRM_API_KEY nelle variabili d'ambiente del servizio."
            )

        for lead in leads:
            lead["created_dt"] = parse_datetime(lead.get("createdAt") or "")
        leads.sort(key=lambda x: x.get("createdAt") or "", reverse=True)

        deposits = sum(1 for lead in leads if lead.get("isDeposit"))
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
    """Manual lead submission form (POST /customer/lead)."""

    template_name = "leads/lead_send.html"
    form_class = LeadSendForm
    success_url = reverse_lazy("leads:list")
    breadcrumb_title = "Send lead"
    breadcrumb_parent = "leads:list"

    def form_valid(self, form):
        try:
            result = client.send_lead(form.to_api_payload(self.request)) or {}
        except client.CRMAPIError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        uuid = result.get("uuid", "n/d")
        toast(self.request, LEVEL_SUCCESS, f"Lead inviato al CRM (uuid: {uuid}).")
        return super().form_valid(form)
