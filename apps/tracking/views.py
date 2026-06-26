from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin

from . import sync as sync_mod
from . import trackbox
from .forms import (
    IrevBrokerForm,
    LandingLeadForm,
    SpmMonsterBrokerForm,
    TrackboxBrokerForm,
)
from .models import (
    IrevBroker,
    Lead,
    PushLog,
    SpmMonsterBroker,
    TrackboxBroker,
    find_broker_by_slug,
)


def _client_ip(request):
    """IP reale del visitatore, dietro Cloudflare/nginx."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def _do_push(lead, broker):
    """Esegue il push (polimorfico sul tipo broker), logga e aggiorna il lead.
    Ritorna il dict risultato normalizzato."""
    res = broker.push(lead)
    PushLog.objects.create(
        lead=lead, broker_label=broker.name, success=res["success"],
        response=res["response"], error=res["error"])
    if res["success"]:
        if res["broker_lead_id"]:
            lead.broker_lead_id = res["broker_lead_id"]
        payload = dict(lead.payload or {})
        if res["login_url"]:
            payload["login_url"] = res["login_url"]
        lead.payload = payload
        lead.save(update_fields=["broker_lead_id", "payload", "updated_at"])
    return res


# ── Landing pubblica ──────────────────────────────────────────────────────
def landing(request, slug):
    """Landing pubblica del broker: il visitatore compila → creiamo il Lead
    (con click_id), lo inviamo al broker e lo reindirizziamo all'auto-login.
    Pubblica (no auth). Funziona per qualsiasi tipo di broker."""
    broker = find_broker_by_slug(slug)
    if broker is None:
        from django.http import Http404
        raise Http404("Landing non trovata")

    if request.method == "POST":
        form = LandingLeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.broker = broker
            lead.ip = _client_ip(request)
            lead.status = "new"
            lead.save()

            res = _do_push(lead, broker)
            if res["success"]:
                if res["login_url"]:
                    return redirect(res["login_url"])
                return render(request, "tracking/landing_thanks.html", {"broker": broker})
            return render(request, "tracking/landing.html",
                          {"broker": broker, "form": form,
                           "push_error": res["error"]}, status=502)
    else:
        form = LandingLeadForm()
    return render(request, "tracking/landing.html", {"broker": broker, "form": form})


# ── Lead ──────────────────────────────────────────────────────────────────
class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Lead
    template_name = "tracking/lead_list.html"
    context_object_name = "leads"
    breadcrumb_title = "Lead"
    paginate_by = 50


class LeadPushView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                   StaffRequiredMixin, View):
    """Invia (push) un lead al suo broker. La lancia lo staff/utente."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        broker = lead.broker
        if broker is None:
            messages.error(request, "Il lead non ha un broker assegnato.")
            return redirect("tracking:lead_list")
        res = _do_push(lead, broker)
        if res["success"]:
            messages.success(request, f"Lead inviato a {broker.name}. id broker: {res['broker_lead_id'] or '—'}")
        else:
            messages.error(request, f"Push fallito ({broker.name}): {res['error']}")
        return redirect("tracking:lead_list")


# ── Broker API — lista unificata (TrackBox + IREV) ────────────────────────
class BrokerListView(BreadcrumbsMixin, LoginRequiredMixin,
                     EmailVerifiedRequiredMixin, StaffRequiredMixin,
                     TemplateView):
    template_name = "tracking/broker_list.html"
    breadcrumb_title = "Broker API"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rows = []
        for b in TrackboxBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:broker_edit", args=[b.pk]),
                "delete_url": reverse("tracking:broker_delete", args=[b.pk]),
                "sync_url": reverse("tracking:broker_sync", args=[b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in IrevBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:irev_edit", args=[b.pk]),
                "delete_url": reverse("tracking:irev_delete", args=[b.pk]),
                "sync_url": None,  # IREV: stato via postback, niente pull manuale
                "landing_slug": b.landing_slug,
            })
        for b in SpmMonsterBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:spm_edit", args=[b.pk]),
                "delete_url": reverse("tracking:spm_delete", args=[b.pk]),
                "sync_url": reverse("tracking:spm_sync", args=[b.pk]),
                "landing_slug": b.landing_slug,
            })
        rows.sort(key=lambda r: r["obj"].name.lower())
        ctx["brokers"] = rows
        return ctx


# ── TrackBox CRUD ─────────────────────────────────────────────────────────
class TrackboxBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, StaffRequiredMixin,
                               CreateView):
    model = TrackboxBroker
    form_class = TrackboxBrokerForm
    template_name = "tracking/broker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker TrackBox"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class TrackboxBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, StaffRequiredMixin,
                               UpdateView):
    model = TrackboxBroker
    form_class = TrackboxBrokerForm
    template_name = "tracking/broker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class TrackboxBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(TrackboxBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class TrackboxBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    """Pull stati per un broker TrackBox (la lancia lo staff)."""

    def post(self, request, pk):
        broker = get_object_or_404(TrackboxBroker, pk=pk)
        try:
            res = sync_mod.sync_broker(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except trackbox.TrackboxError as exc:
            messages.error(request, f"Sync {broker.name} fallita: {exc}")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── IREV CRUD ─────────────────────────────────────────────────────────────
class IrevBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           CreateView):
    model = IrevBroker
    form_class = IrevBrokerForm
    template_name = "tracking/irev_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker IREV"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class IrevBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           UpdateView):
    model = IrevBroker
    form_class = IrevBrokerForm
    template_name = "tracking/irev_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class IrevBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(IrevBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


# ── SPM Monster CRUD + sync ───────────────────────────────────────────────
class SpmMonsterBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, StaffRequiredMixin,
                                 CreateView):
    model = SpmMonsterBroker
    form_class = SpmMonsterBrokerForm
    template_name = "tracking/spm_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker SPM Monster"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class SpmMonsterBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, StaffRequiredMixin,
                                 UpdateView):
    model = SpmMonsterBroker
    form_class = SpmMonsterBrokerForm
    template_name = "tracking/spm_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class SpmMonsterBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                 StaffRequiredMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(SpmMonsterBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class SpmMonsterBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    """Pull stati per un broker SPM Monster (la lancia lo staff)."""

    def post(self, request, pk):
        broker = get_object_or_404(SpmMonsterBroker, pk=pk)
        try:
            res = sync_mod.sync_spmmonster(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")
