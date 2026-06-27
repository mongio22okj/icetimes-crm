from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
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
    broker_by_kind,
    find_broker_by_slug,
)


class AdminOnlyMixin(UserPassesTestMixin):
    """Accesso solo Super Admin (superuser o role 'admin').
    Usato per config broker, chiavi API e azioni che toccano i broker.
    Marketer/Visualizzatore → 403."""
    raise_exception = True

    def test_func(self):
        u = self.request.user
        return bool(u.is_authenticated and u.is_crm_admin)


class MarketerOrAdminMixin(UserPassesTestMixin):
    """Accesso a Super Admin + Marketer (call center). Visualizzatore → 403."""
    raise_exception = True

    def test_func(self):
        u = self.request.user
        return bool(u.is_authenticated and (u.is_crm_admin or u.is_crm_marketer))


def build_form_snippet(action_url):
    """Snippet <form> pronto da incollare nella landing ESTERNA del broker.
    Postando a action_url i campi vengono catturati e attribuiti a quel broker."""
    return (
        '<form method="POST" action="%s">\n'
        '  <input type="text"  name="firstname" placeholder="Nome" required>\n'
        '  <input type="text"  name="lastname"  placeholder="Cognome">\n'
        '  <input type="email" name="email"     placeholder="Email" required>\n'
        '  <input type="tel"   name="phone"     placeholder="Telefono" required>\n'
        '  <input type="text"  name="country"   value="IT" maxlength="2">\n'
        '  <button type="submit">Inizia ora</button>\n'
        '</form>' % action_url
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
        if lead.stage == "nuovo":
            lead.stage = "inviato"
        lead.save(update_fields=["broker_lead_id", "payload", "stage", "updated_at"])
    return res


# ── Landing pubblica + antifrode ──────────────────────────────────────────
def _rate_limited(ip, limit=5, window=60):
    """True se questo IP ha superato `limit` invii in `window` secondi."""
    from django.core.cache import cache
    if not ip:
        return False
    key = f"lp_rl:{ip}"
    n = cache.get(key, 0)
    if n >= limit:
        return True
    cache.set(key, n + 1, window)
    return False


def _is_duplicate(broker, email, phone):
    """True se per QUESTO broker esiste già un lead con stessa email o telefono."""
    from django.db.models import Q
    cond = Q()
    if email:
        cond |= Q(email__iexact=email)
    if phone:
        cond |= Q(phone=phone)
    if not cond.children:
        return False
    return Lead.for_broker(broker).filter(cond).exists()


def _landing_render(request, broker, form, error=None, status=200):
    """Serve l'HTML custom del broker se presente, altrimenti il form standard."""
    if broker.landing_html:
        return HttpResponse(broker.landing_html, status=status)
    ctx = {"broker": broker, "form": form}
    if error:
        ctx["push_error"] = error
    return render(request, "tracking/landing.html", ctx, status=status)


@csrf_exempt
def landing(request, slug):
    """Landing pubblica del broker (la SUA: landing_html dedicato o form standard).
    Antifrode: honeypot (nel form), rate-limit per IP, deduplica per broker.
    Visitatore compila → Lead (click_id) → push → redirect auto-login."""
    broker = find_broker_by_slug(slug)
    if broker is None:
        raise Http404("Landing non trovata")

    form = LandingLeadForm(request.POST or None)
    if request.method == "POST":
        ip = _client_ip(request)
        if _rate_limited(ip):
            return _landing_render(request, broker, form,
                                   "Troppi invii, riprova tra poco.", 429)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            phone = form.cleaned_data.get("phone")
            if _is_duplicate(broker, email, phone):
                return _landing_render(request, broker, form,
                                       "Lead già registrato.", 409)
            lead = form.save(commit=False)
            lead.broker = broker
            lead.ip = ip
            lead.status = "new"
            lead.save()
            res = _do_push(lead, broker)
            if res["success"]:
                if res["login_url"]:
                    return redirect(res["login_url"])
                return render(request, "tracking/landing_thanks.html", {"broker": broker})
            return _landing_render(request, broker, form, res["error"], 502)
        # form non valido (honeypot / validazione)
        return _landing_render(request, broker, form, status=400)

    return _landing_render(request, broker, form)


# ── Lead (lettura: tutti gli staff) ───────────────────────────────────────
class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Lead
    template_name = "tracking/lead_list.html"
    context_object_name = "leads"
    breadcrumb_title = "Lead"
    paginate_by = 50

    def get_queryset(self):
        qs = Lead.objects.all()
        g = self.request.GET
        for param, field in (
            ("firstname", "firstname__icontains"),
            ("lastname", "lastname__icontains"),
            ("email", "email__icontains"),
            ("phone", "phone__icontains"),
            ("ip", "ip__icontains"),
            ("country", "country__icontains"),
            ("status", "status__icontains"),
            ("note", "note__icontains"),
            ("click_id", "click_id__icontains"),
        ):
            v = (g.get(param) or "").strip()
            if v:
                qs = qs.filter(**{field: v})
        dep = g.get("deposit") or ""
        if dep == "1":
            qs = qs.filter(is_deposit=True)
        elif dep == "0":
            qs = qs.filter(is_deposit=False)
        st = g.get("stage") or ""
        if st:
            qs = qs.filter(stage=st)
        bv = g.get("broker") or ""
        if ":" in bv:
            from django.contrib.contenttypes.models import ContentType
            k, _, pid = bv.partition(":")
            b = broker_by_kind(k, pid)
            if b:
                ct = ContentType.objects.get_for_model(type(b))
                qs = qs.filter(broker_content_type=ct, broker_object_id=b.pk)
        return qs

    def get_context_data(self, **kwargs):
        from .models import all_brokers
        ctx = super().get_context_data(**kwargs)
        ctx["broker_options"] = [{"value": f"{b.kind}:{b.pk}", "name": b.name}
                                 for b in all_brokers()]
        ctx["stage_choices"] = Lead.STAGE_CHOICES
        u = self.request.user
        ctx["can_edit_stage"] = bool(u.is_crm_admin or u.is_crm_marketer)
        return ctx


class LeadStageUpdateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                          MarketerOrAdminMixin, View):
    """Transizione manuale della fase del lead (call center). Admin + Marketer."""

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        valid = dict(Lead.STAGE_CHOICES)
        stage = request.POST.get("stage") or lead.stage
        if stage in valid:
            lead.stage = stage
            lead.reject_reason = ((request.POST.get("reject_reason") or "").strip()
                                  if stage == "rifiutato" else "")
            lead.save(update_fields=["stage", "reject_reason", "updated_at"])
            messages.success(request, f"Fase aggiornata: {valid[stage]}.")
        return redirect(request.POST.get("next") or "tracking:lead_list")


class LeadSyncSelectedView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           MarketerOrAdminMixin, View):
    """Pull/sync dello stato dal broker SOLO per i lead selezionati."""

    def post(self, request):
        ids = request.POST.getlist("lead_ids")
        if not ids:
            messages.warning(request, "Nessun lead selezionato.")
            return redirect(request.POST.get("next") or "tracking:lead_list")
        r = sync_mod.sync_selected(ids)
        messages.success(
            request,
            f"Aggiornati {r['updated']} lead ({r['matched']} agganciati su "
            f"{len(ids)} selezionati, {r['brokers']} broker).")
        if r.get("irev"):
            messages.info(request,
                          f"{r['irev']} broker IREV saltati (stato via postback).")
        if r["errors"]:
            messages.error(request, "Errori: " + "; ".join(r["errors"]))
        return redirect(request.POST.get("next") or "tracking:lead_list")


class LeadPushView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                   AdminOnlyMixin, View):
    """Invia (push) un lead al suo broker. Solo Super Admin."""

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


# ── Broker API — solo Super Admin (config + chiavi) ───────────────────────
class BrokerListView(BreadcrumbsMixin, LoginRequiredMixin,
                     EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in IrevBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:irev_edit", args=[b.pk]),
                "delete_url": reverse("tracking:irev_delete", args=[b.pk]),
                "sync_url": None,  # IREV: stato via postback, niente pull manuale
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in SpmMonsterBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:spm_edit", args=[b.pk]),
                "delete_url": reverse("tracking:spm_delete", args=[b.pk]),
                "sync_url": reverse("tracking:spm_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        rows.sort(key=lambda r: r["obj"].name.lower())
        ctx["brokers"] = rows
        return ctx


# ── TrackBox CRUD (solo Super Admin) ──────────────────────────────────────
class TrackboxBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                               AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(TrackboxBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class TrackboxBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             AdminOnlyMixin, View):
    """Pull stati per un broker TrackBox (solo Super Admin)."""

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


# ── IREV CRUD (solo Super Admin) ──────────────────────────────────────────
class IrevBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                           EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                           AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(IrevBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


# ── SPM Monster CRUD + sync (solo Super Admin) ────────────────────────────
class SpmMonsterBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
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
                                 AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(SpmMonsterBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class SpmMonsterBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    """Pull stati per un broker SPM Monster (solo Super Admin)."""

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


# ── Sync-all + Guida (tutti gli staff) ────────────────────────────────────
class SyncAllView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                  StaffRequiredMixin, View):
    """Pulsante 'aggiorna lead': pull/sync di TUTTI i broker pull-capable."""

    def post(self, request):
        r = sync_mod.sync_all_pullable()
        messages.success(
            request,
            f"Lead aggiornati: {r['updated']} ({r['matched']} agganciati su "
            f"{r['seen']} righe, {r['brokers']} broker).")
        if r["errors"]:
            messages.error(request, "Errori: " + "; ".join(r["errors"]))
        return redirect(request.POST.get("next") or "dashboard")


class GuideView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin,
                StaffRequiredMixin, TemplateView):
    """Guida statica: come funziona il CRM, passo per passo."""
    template_name = "tracking/guide.html"
    breadcrumb_title = "Guida"


# ── Codice tracciamento per landing ESTERNA (solo Super Admin) ────────────
class TrackingCodeView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, AdminOnlyMixin,
                       TemplateView):
    """Mostra lo snippet <form> da incollare nella landing esterna del broker."""
    template_name = "tracking/tracking_code.html"
    breadcrumb_title = "Codice tracciamento"
    breadcrumb_parent = "tracking:broker_list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        broker = broker_by_kind(self.kwargs["kind"], self.kwargs["pk"])
        if broker is None:
            raise Http404("Broker non trovato")
        ctx["broker"] = broker
        slug = broker.landing_slug
        if slug:
            url = self.request.build_absolute_uri(f"/lp/{slug}/")
            ctx["landing_url"] = url
            ctx["snippet"] = build_form_snippet(url)
        return ctx
