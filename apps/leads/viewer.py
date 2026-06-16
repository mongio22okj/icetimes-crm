"""Area visualizzatori — accesso SOLA LETTURA ai lead in arrivo.

Utenti non-staff entrano col proprio login (l'area /viewer/ è esente dal
gate Basic-Auth del sito, vedi SITE_GATE_EXEMPT_PREFIXES) e vedono solo la
lista dei lead, senza poter modificare nulla né raggiungere il CRM (le
pagine staff restano dietro il gate + StaffRequiredMixin).
"""
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from .models import Lead


def _lead_rows(limit: int = 100):
    rows = []
    for l in Lead.objects.order_by("-created_at")[:limit]:
        rows.append({
            "created": timezone.localtime(l.created_at).strftime("%d/%m/%Y %H:%M"),
            "name": l.full_name or "—",
            "email": l.email or "—",
            "phone": l.phone or "—",
            "country": (l.country or "—").upper(),
            "source": l.source or "—",
            "status": l.status or "—",
            "score": l.score,
        })
    return rows


class ViewerLoginView(auth_views.LoginView):
    template_name = "viewer/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("viewer:dashboard")

    def get_success_url(self):
        return str(self.next_page)


class ViewerLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("viewer:login")


class ViewerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "viewer/dashboard.html"
    login_url = reverse_lazy("viewer:login")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["leads"] = _lead_rows()
        ctx["total"] = Lead.objects.count()
        return ctx


class ViewerDataView(View):
    """Endpoint JSON per l'auto-refresh della tabella (solo loggati)."""

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "auth"}, status=401)
        return JsonResponse({"leads": _lead_rows(), "total": Lead.objects.count()})
