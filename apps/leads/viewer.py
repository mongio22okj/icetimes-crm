"""Area visualizzatori — accesso SOLA LETTURA ai lead in arrivo.

Flusso: il visualizzatore si auto-registra (user + password) → l'account
nasce DISATTIVO (is_active=False) e non può entrare. Lo staff, dal pannello
centrale (/leads/viewers/), approva o rifiuta. Solo dopo l'approvazione il
visualizzatore può loggarsi e vedere i lead — niente modifica, niente CRM
(le pagine staff restano dietro il gate Basic-Auth + StaffRequiredMixin).
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, TemplateView

from .models import Lead

User = get_user_model()
VIEWER_GROUP = "Viewers"


def viewer_group() -> Group:
    grp, _ = Group.objects.get_or_create(name=VIEWER_GROUP)
    return grp


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


# ── Registrazione ────────────────────────────────────────────────────────
class ViewerRegisterForm(forms.Form):
    username = forms.CharField(max_length=150, label="Utente")
    password = forms.CharField(min_length=8, widget=forms.PasswordInput,
                               label="Password", help_text="Almeno 8 caratteri.")

    def clean_username(self):
        u = (self.cleaned_data["username"] or "").strip()
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Username già in uso, scegline un altro.")
        return u


class ViewerRegisterView(FormView):
    template_name = "viewer/register.html"
    form_class = ViewerRegisterForm

    def form_valid(self, form):
        user = User(username=form.cleaned_data["username"],
                    is_active=False, is_staff=False)
        user.set_password(form.cleaned_data["password"])
        user.save()
        user.groups.add(viewer_group())
        return self.render_to_response(self.get_context_data(submitted=True))


# ── Login / logout ───────────────────────────────────────────────────────
class ViewerLoginView(auth_views.LoginView):
    template_name = "viewer/login.html"
    redirect_authenticated_user = True
    next_page = reverse_lazy("viewer:dashboard")

    def get_success_url(self):
        return str(self.next_page)

    def form_invalid(self, form):
        # ModelBackend rifiuta gli utenti inattivi come "credenziali errate".
        # Se le credenziali sono giuste ma l'account è in attesa, mostriamo
        # un messaggio chiaro invece di "utente/password non validi".
        username = (self.request.POST.get("username") or "").strip()
        password = self.request.POST.get("password") or ""
        if username and password:
            u = User.objects.filter(username__iexact=username,
                                    is_active=False).first()
            if u and u.check_password(password):
                return self.render_to_response(
                    self.get_context_data(form=form, pending=True))
        return super().form_invalid(form)


class ViewerLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("viewer:login")


# ── Dashboard sola lettura ───────────────────────────────────────────────
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
