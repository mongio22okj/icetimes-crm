from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin

from . import sync as sync_mod
from . import trackbox
from .forms import LandingLeadForm, TrackboxBrokerForm
from .models import Lead, PushLog, TrackboxBroker


def _client_ip(request):
    """IP reale del visitatore, dietro Cloudflare/nginx."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def landing(request, slug):
    """Landing pubblica del broker: il visitatore compila → creiamo il Lead
    (con click_id), lo inviamo al broker e lo reindirizziamo all'auto-login.

    Pubblica (no auth). Il PUSH reale parte da qui quando un utente compila
    davvero il form — è il flusso di test/produzione (browser+dati+IP reali)."""
    broker = get_object_or_404(TrackboxBroker, landing_slug=slug, is_active=True)

    if request.method == "POST":
        form = LandingLeadForm(request.POST)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.broker = broker
            lead.ip = _client_ip(request)
            lead.status = "new"
            lead.save()

            success, error, response = False, "", {}
            try:
                response = trackbox.push_lead(broker, lead) or {}
                success = True
            except trackbox.TrackboxError as exc:
                error = str(exc)[:255]
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"[:255]

            PushLog.objects.create(
                lead=lead, broker=broker, success=success,
                response=response if isinstance(response, dict) else {"raw": str(response)[:1000]},
                error=error,
            )

            if success:
                bid = trackbox.extract_broker_lead_id(response)
                login_url = trackbox.extract_login_url(response)
                if bid:
                    lead.broker_lead_id = bid
                payload = dict(lead.payload or {})
                if login_url:
                    payload["login_url"] = login_url
                lead.payload = payload
                lead.save(update_fields=["broker_lead_id", "payload", "updated_at"])
                if login_url:
                    return redirect(login_url)
                return render(request, "tracking/landing_thanks.html", {"broker": broker})
            return render(request, "tracking/landing.html",
                          {"broker": broker, "form": form,
                           "push_error": error}, status=502)
    else:
        form = LandingLeadForm()

    return render(request, "tracking/landing.html", {"broker": broker, "form": form})


class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin,
                   ListView):
    model = Lead
    template_name = "tracking/lead_list.html"
    context_object_name = "leads"
    breadcrumb_title = "Lead"
    paginate_by = 50

    def get_queryset(self):
        return super().get_queryset().select_related("broker")


class LeadPushView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                   StaffRequiredMixin, View):
    """Invia (push) un lead al suo broker. L'azione la lancia lo staff/utente;
    il client fa la chiamata server→broker e registra l'esito in PushLog."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        broker = lead.broker
        if broker is None:
            messages.error(request, "Il lead non ha un broker assegnato.")
            return redirect("tracking:lead_list")

        success, error, response = False, "", {}
        try:
            response = trackbox.push_lead(broker, lead) or {}
            success = True
        except trackbox.TrackboxError as exc:
            error = str(exc)[:255]
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"[:255]

        PushLog.objects.create(
            lead=lead, broker=broker, success=success,
            response=response if isinstance(response, dict) else {"raw": str(response)[:1000]},
            error=error,
        )

        if success:
            bid = trackbox.extract_broker_lead_id(response)
            login_url = trackbox.extract_login_url(response)
            if bid:
                lead.broker_lead_id = bid
            payload = dict(lead.payload or {})
            if login_url:
                payload["login_url"] = login_url
            lead.payload = payload
            lead.save(update_fields=["broker_lead_id", "payload", "updated_at"])
            messages.success(request, f"Lead inviato a {broker.name}. id broker: {bid or '—'}")
        else:
            messages.error(request, f"Push fallito ({broker.name}): {error}")
        return redirect("tracking:lead_list")


class TrackboxBrokerListView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             ListView):
    model = TrackboxBroker
    template_name = "tracking/broker_list.html"
    context_object_name = "brokers"
    breadcrumb_title = "Broker API"


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
        response = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return response


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
        response = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return response


class TrackboxBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    def post(self, request, pk):
        broker = get_object_or_404(TrackboxBroker, pk=pk)
        name = broker.name
        broker.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class TrackboxBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    """Lancia la PULL degli stati per un broker. L'azione la lancia lo staff
    (è una chiamata al broker); aggiorna i nostri lead e mostra un riepilogo."""

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
