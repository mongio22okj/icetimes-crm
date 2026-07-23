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
    OpenAffBrokerForm,
    GlobalTradeBrokerForm,
    OneCryptBrokerForm,
    CpaForgeBrokerForm,
    AffinitraxBrokerForm,
    LeadShakerBrokerForm,
    SpmMonsterBrokerForm,
    GalassiaBrokerForm,
    TYourAdsBrokerForm,
    TrackboxBrokerForm,
)
from .models import (
    IrevBroker,
    Lead,
    OpenAffBroker,
    GlobalTradeBroker,
    OneCryptBroker,
    CpaForgeBroker,
    AffinitraxBroker,
    LeadShakerBroker,
    PushLog,
    SpmMonsterBroker,
    GalassiaBroker,
    TYourAdsBroker,
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
        lead.save(update_fields=["broker_lead_id", "payload", "updated_at"])
    else:
        # Un 504 / timeout NON è un rifiuto: il lead viene comunque registrato
        # lato broker (confermato). Lo marchiamo così NON finisce tra gli errori
        # ma tra i Lead validi; il sync poi backfilla broker_lead_id.
        _e = str(res.get("error") or "").lower()
        if any(t in _e for t in ("504", "timeout", "time out", "timed out")):
            payload = dict(lead.payload or {})
            payload["push_timeout"] = True
            lead.payload = payload
            lead.save(update_fields=["payload", "updated_at"])
    try:
        from .telegram_notify import notify_new_lead
        notify_new_lead(lead, res)
    except Exception:  # noqa: BLE001
        pass
    try:
        from .sheets_notify import notify_sheets
        notify_sheets(lead, res)
    except Exception:  # noqa: BLE001
        pass
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


def _duplicate_reason(broker, email, phone, ip, firstname, lastname):
    """Antifrode per-broker. Ritorna il MOTIVO del duplicato (str) o None.

    Sullo STESSO broker bloccano da soli: stessa email, stesso telefono,
    stesso nome+cognome. L'IP blocca solo se combinato con uno di questi
    (gli IP condivisi — mobile/ufficio — darebbero troppi falsi positivi)."""
    from django.db.models import Q
    qs = Lead.for_broker(broker)
    # "Ripartenza" antifrode: se il broker ha una data dedup_since (es. cambio
    # broker/piattaforma), consideriamo solo i lead da quella data in poi, così
    # chi si era iscritto PRIMA non blocca le nuove registrazioni.
    cutoff = getattr(broker, "dedup_since", None)
    if cutoff:
        qs = qs.filter(created_at__gte=cutoff)
    email = (email or "").strip()
    phone = (phone or "").strip()
    fn = (firstname or "").strip()
    ln = (lastname or "").strip()

    if email and qs.filter(email__iexact=email).exists():
        return "email"
    if phone and qs.filter(phone=phone).exists():
        return "telefono"
    if fn and ln and qs.filter(firstname__iexact=fn, lastname__iexact=ln).exists():
        return "nome"
    if ip:
        combo = Q()
        if email:
            combo |= Q(email__iexact=email)
        if phone:
            combo |= Q(phone=phone)
        if fn and ln:
            combo |= (Q(firstname__iexact=fn) & Q(lastname__iexact=ln))
        if combo.children and qs.filter(Q(ip=ip) & combo).exists():
            return "ip"
    return None


def _landing_render(request, broker, form, error=None, status=200):
    """Serve l'HTML custom del broker se presente, altrimenti il form standard.
    Se c'e' un errore (duplicato / rate-limit / validazione), inietta un banner
    ben visibile in cima alla landing personalizzata, cosi il visitatore capisce
    perche' il form non e' andato (prima ricaricava muto -> sembrava 'torna indietro')."""
    if broker.landing_html:
        html_doc = broker.landing_html
        if error:
            import html as _html
            import re as _re
            banner = (
                '<div style="position:fixed;top:0;left:0;right:0;z-index:2147483647;'
                'background:#dc2626;color:#fff;text-align:center;padding:13px 18px;'
                'font:600 15px -apple-system,Segoe UI,Roboto,Arial,sans-serif;'
                'box-shadow:0 2px 12px rgba(0,0,0,.3)">%s</div>'
                '<div style="height:46px"></div>'
                % _html.escape(str(error))
            )
            m = _re.search(r"<body[^>]*>", html_doc, _re.I)
            html_doc = (html_doc[:m.end()] + banner + html_doc[m.end():]
                        if m else banner + html_doc)
        return HttpResponse(html_doc, status=status)
    ctx = {"broker": broker, "form": form}
    if error:
        ctx["push_error"] = error
    return render(request, "tracking/landing.html", ctx, status=status)


_LP_DONE_COOKIE = "lp_done"
_LP_DONE_MAX_AGE = 60 * 60 * 24 * 365  # 1 anno


def _set_lp_done(response, slug):
    """Marca questo browser come 'ha già inviato' su QUESTA landing.
    Cookie con path per-landing: le altre landing/broker restano libere."""
    response.set_cookie(_LP_DONE_COOKIE, "1", max_age=_LP_DONE_MAX_AGE,
                        path=f"/lp/{slug}/", samesite="Lax", httponly=True)
    return response


@csrf_exempt
def landing(request, slug):
    """Landing pubblica del broker (la SUA: landing_html dedicato o form standard).
    Antifrode: honeypot (nel form), rate-limit per IP, deduplica per broker,
    blocco one-shot per browser (cookie): dopo l'invio il form non viene più
    servito, nemmeno ricaricando la pagina.
    Visitatore compila → Lead (click_id) → push → redirect auto-login."""
    broker = find_broker_by_slug(slug)
    if broker is None:
        raise Http404("Landing non trovata")

    # Blocco one-shot: questo browser ha già inviato su questa landing.
    if request.COOKIES.get(_LP_DONE_COOKIE):
        return render(request, "tracking/landing_thanks.html",
                      {"broker": broker, "login_url": "", "already_done": True})

    form = LandingLeadForm(request.POST or None)
    if request.method == "POST":
        ip = _client_ip(request)
        if _rate_limited(ip):
            return _landing_render(request, broker, form,
                                   "Troppi invii, riprova tra poco.", 429)
        if form.is_valid():
            cd = form.cleaned_data
            reason = _duplicate_reason(
                broker, cd.get("email"), cd.get("phone"), ip,
                cd.get("firstname"), cd.get("lastname"))
            lead = form.save(commit=False)
            lead.broker = broker
            lead.ip = ip
            if reason:
                # Duplicato: si salva nel CRM (riga rossa) ma NON si invia al
                # broker. Nessuna chiamata: la push viene saltata del tutto.
                lead.is_duplicate = True
                lead.duplicate_reason = reason
                lead.status = "DUPLICATO"
                lead.save()
                return _set_lp_done(
                    render(request, "tracking/landing_duplicate.html",
                           {"broker": broker}, status=409), slug)
            lead.status = "new"
            lead.save()
            res = _do_push(lead, broker)
            return _set_lp_done(render(request, "tracking/landing_thanks.html", {
                "broker": broker,
                "login_url": res.get("login_url") or "",
            }), slug)






        # form non valido (honeypot / validazione)
        return _landing_render(request, broker, form,
                               "Controlla i dati inseriti e riprova.", status=400)

    return _landing_render(request, broker, form)


# ── Lead (lettura: tutti gli staff) ───────────────────────────────────────
class LeadListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, ListView):
    model = Lead
    template_name = "tracking/lead_list.html"
    context_object_name = "leads"
    breadcrumb_title = "Lead"
    paginate_by = 50
    error_only = False  # True nella pagina "Landing Errore"

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
        # Separazione: nella pagina Lead restano SOLO i lead VALIDI = CONSEGNATI
        # al broker e NON di test. "Consegnato" = ha l'auto-login OPPURE un
        # broker_lead_id (anche backfillato dalla pull) OPPURE è stato visto
        # dalla pull (last_pull_at) OPPURE è un timeout/504 (registrato lato
        # broker). Push RIFIUTATI davvero (400, mai registrati), duplicati
        # (rossi) e lead di test vanno nella pagina "Landing Errore".
        from django.db.models import Q
        test_q = (Q(firstname__icontains="test") | Q(lastname__icontains="test")
                  | Q(email__icontains="test") | Q(status__iexact="test"))
        delivered_q = (Q(payload__has_key="login_url")
                       | ~Q(broker_lead_id="")
                       | Q(last_pull_at__isnull=False)
                       | Q(payload__push_timeout=True))
        # force_error: lead RIFIUTATO dal broker al push che vogliamo in
        # "Landing Errore" anche se poi ha ottenuto un broker_lead_id o e'
        # comparso nella pull. Si marca a mano in payload; reversibile.
        # NB: has_key e NON payload__force_error=True — su una chiave assente
        # il confronto vale NULL e l'exclude scarterebbe tutte le righe.
        forced_q = Q(payload__has_key="force_error")
        if self.error_only:
            qs = qs.filter(~delivered_q | test_q | forced_q)
        else:
            qs = qs.filter(delivered_q).exclude(test_q).exclude(forced_q)
        return qs

    def get_context_data(self, **kwargs):
        from .models import all_brokers
        ctx = super().get_context_data(**kwargs)
        ctx["broker_options"] = [{"value": f"{b.kind}:{b.pk}", "name": b.name}
                                 for b in sorted(all_brokers(), key=lambda b: b.name.lower())]
        ctx["stage_choices"] = Lead.STAGE_CHOICES
        u = self.request.user
        ctx["can_edit_stage"] = bool(u.is_crm_admin or u.is_crm_marketer)
        # Segnare una FTD come "pagata" e' un'azione contabile: solo Super Admin.
        ctx["can_mark_paid"] = bool(u.is_crm_admin)
        ctx["error_only"] = self.error_only
        from django.db.models import Q
        _tq = (Q(firstname__icontains="test") | Q(lastname__icontains="test")
               | Q(email__icontains="test") | Q(status__iexact="test"))
        _delivered = (Q(payload__has_key="login_url")
                      | ~Q(broker_lead_id="")
                      | Q(last_pull_at__isnull=False)
                      | Q(payload__push_timeout=True))
        ctx["error_count"] = Lead.objects.filter(
            ~_delivered | _tq | Q(payload__has_key="force_error")).count()
        return ctx


class LeadErrorListView(LeadListView):
    """Pagina 'Landing Errore': SOLO i lead con push fallito (senza auto-login)."""
    error_only = True
    breadcrumb_title = "Landing Errore"


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


class LeadTogglePaidView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                         AdminOnlyMixin, View):
    """Segna / annulla una FTD come 'gia' pagata' (payout incassato).

    Solo Super Admin. Sposta la FTD dal 'Guadagno da incassare' all''Incassato'
    nella dashboard CRM e la colora AZZURRA nella tabella Lead.
    """

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        nxt = request.POST.get("next") or "tracking:lead_list"
        if not lead.is_deposit:
            messages.warning(request, "Solo le FTD possono essere segnate come pagate.")
            return redirect(nxt)
        lead.ftd_paid = not lead.ftd_paid
        lead.save(update_fields=["ftd_paid", "updated_at"])
        who = lead.full_name or lead.email or lead.click_id
        if lead.ftd_paid:
            messages.success(request, f"FTD di {who} segnata come PAGATA (incassata).")
        else:
            messages.info(request, f"FTD di {who} rimessa come DA INCASSARE.")
        return redirect(nxt)


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
        for b in GalassiaBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:galassia_edit", args=[b.pk]),
                "delete_url": reverse("tracking:galassia_delete", args=[b.pk]),
                "sync_url": reverse("tracking:galassia_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in TYourAdsBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:tyourads_edit", args=[b.pk]),
                "delete_url": reverse("tracking:tyourads_delete", args=[b.pk]),
                "sync_url": None,  # TYourAds: nessun pull noto (stato via postback)
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in OpenAffBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:openaff_edit", args=[b.pk]),
                "delete_url": reverse("tracking:openaff_delete", args=[b.pk]),
                "sync_url": reverse("tracking:openaff_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in GlobalTradeBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:globaltrade_edit", args=[b.pk]),
                "delete_url": reverse("tracking:globaltrade_delete", args=[b.pk]),
                "sync_url": reverse("tracking:globaltrade_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in OneCryptBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:onecrypt_edit", args=[b.pk]),
                "delete_url": reverse("tracking:onecrypt_delete", args=[b.pk]),
                "sync_url": reverse("tracking:onecrypt_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in CpaForgeBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:cpaforge_edit", args=[b.pk]),
                "delete_url": reverse("tracking:cpaforge_delete", args=[b.pk]),
                "sync_url": reverse("tracking:cpaforge_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in AffinitraxBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:affinitrax_edit", args=[b.pk]),
                "delete_url": reverse("tracking:affinitrax_delete", args=[b.pk]),
                "sync_url": reverse("tracking:affinitrax_sync", args=[b.pk]),
                "code_url": reverse("tracking:broker_code", args=[b.kind, b.pk]),
                "landing_slug": b.landing_slug,
            })
        for b in LeadShakerBroker.objects.all():
            rows.append({
                "obj": b, "kind": b.kind_label, "base_url": b.base_url,
                "is_active": b.is_active, "note": b.note,
                "edit_url": reverse("tracking:leadshaker_edit", args=[b.pk]),
                "delete_url": reverse("tracking:leadshaker_delete", args=[b.pk]),
                "sync_url": reverse("tracking:leadshaker_sync", args=[b.pk]),
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
    """Pulsante 'aggiorna lead': lancia la pull/sync di TUTTI i broker in
    BACKGROUND e risponde subito (la sync completa può richiedere minuti:
    i broker vengono interrogati uno per uno). Gli stessi aggiornamenti
    girano comunque in automatico via cron ogni 5 minuti."""

    def post(self, request):
        import threading

        def _run():
            try:
                sync_mod.sync_all_pullable()
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_run, daemon=True,
                         name="sync-all-background").start()
        messages.success(
            request,
            "Aggiornamento avviato in background: gli stati si aggiornano da "
            "soli tra qualche istante — puoi continuare a lavorare.")
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


class TYourAdsBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               CreateView):
    model = TYourAdsBroker
    form_class = TYourAdsBrokerForm
    template_name = "tracking/tyourads_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker TYourAds"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class TYourAdsBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               UpdateView):
    model = TYourAdsBroker
    form_class = TYourAdsBrokerForm
    template_name = "tracking/tyourads_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class TYourAdsBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(TYourAdsBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class GalassiaBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               CreateView):
    model = GalassiaBroker
    form_class = GalassiaBrokerForm
    template_name = "tracking/galassia_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker Galassia"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class GalassiaBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               UpdateView):
    model = GalassiaBroker
    form_class = GalassiaBrokerForm
    template_name = "tracking/galassia_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class GalassiaBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(GalassiaBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class GalassiaBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             AdminOnlyMixin, View):
    """Pull stati per un broker Galassia (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(GalassiaBroker, pk=pk)
        try:
            res = sync_mod.sync_galassia(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati, "
                f"{res['matched']} agganciati.")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} fallito: {exc}")
        return redirect("tracking:broker_list")


# ── OpenAFF CRUD + sync (solo Super Admin) ────────────────────────────────
class OpenAffBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                              EmailVerifiedRequiredMixin, AdminOnlyMixin,
                              CreateView):
    model = OpenAffBroker
    form_class = OpenAffBrokerForm
    template_name = "tracking/openaff_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker OpenAFF"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class OpenAffBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                              EmailVerifiedRequiredMixin, AdminOnlyMixin,
                              UpdateView):
    model = OpenAffBroker
    form_class = OpenAffBrokerForm
    template_name = "tracking/openaff_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class OpenAffBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                              AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(OpenAffBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class OpenAffBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            AdminOnlyMixin, View):
    """Pull stati per un broker OpenAFF (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(OpenAffBroker, pk=pk)
        try:
            res = sync_mod.sync_openaff(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── GlobalTrade CRUD + sync (solo Super Admin) ────────────────────────────
class GlobalTradeBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                                  EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                  CreateView):
    model = GlobalTradeBroker
    form_class = GlobalTradeBrokerForm
    template_name = "tracking/globaltrade_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker GlobalTrade"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class GlobalTradeBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                                  EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                  UpdateView):
    model = GlobalTradeBroker
    form_class = GlobalTradeBrokerForm
    template_name = "tracking/globaltrade_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class GlobalTradeBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                  AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(GlobalTradeBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class GlobalTradeBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                AdminOnlyMixin, View):
    """Pull stati per un broker GlobalTrade (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(GlobalTradeBroker, pk=pk)
        try:
            res = sync_mod.sync_globaltrade(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── OneCrypt CRUD + sync (solo Super Admin) ───────────────────────────────
class OneCryptBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               CreateView):
    model = OneCryptBroker
    form_class = OneCryptBrokerForm
    template_name = "tracking/onecrypt_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker OneCrypt"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class OneCryptBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               UpdateView):
    model = OneCryptBroker
    form_class = OneCryptBrokerForm
    template_name = "tracking/onecrypt_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class OneCryptBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(OneCryptBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class OneCryptBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             AdminOnlyMixin, View):
    """Pull stati per un broker OneCrypt (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(OneCryptBroker, pk=pk)
        try:
            res = sync_mod.sync_onecrypt(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── CPAForge CRUD + sync (solo Super Admin) ───────────────────────────────
class CpaForgeBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               CreateView):
    model = CpaForgeBroker
    form_class = CpaForgeBrokerForm
    template_name = "tracking/cpaforge_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker CPAForge"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class CpaForgeBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                               EmailVerifiedRequiredMixin, AdminOnlyMixin,
                               UpdateView):
    model = CpaForgeBroker
    form_class = CpaForgeBrokerForm
    template_name = "tracking/cpaforge_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class CpaForgeBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(CpaForgeBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class CpaForgeBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             AdminOnlyMixin, View):
    """Pull stati per un broker CPAForge (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(CpaForgeBroker, pk=pk)
        try:
            res = sync_mod.sync_cpaforge(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── Affinitrax CRUD (solo Super Admin) ─────────────────────────────────────
class AffinitraxBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                 CreateView):
    model = AffinitraxBroker
    form_class = AffinitraxBrokerForm
    template_name = "tracking/affinitrax_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker Affinitrax"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class AffinitraxBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                 UpdateView):
    model = AffinitraxBroker
    form_class = AffinitraxBrokerForm
    template_name = "tracking/affinitrax_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class AffinitraxBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                 AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(AffinitraxBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class AffinitraxBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    """Pull stati per un broker Affinitrax (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(AffinitraxBroker, pk=pk)
        try:
            res = sync_mod.sync_affinitrax(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


# ── Lead-Shaker CRUD (solo Super Admin) ────────────────────────────────────
class LeadShakerBrokerCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                 CreateView):
    model = LeadShakerBroker
    form_class = LeadShakerBrokerForm
    template_name = "tracking/leadshaker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_title = "Nuovo broker Lead-Shaker"
    breadcrumb_parent = "tracking:broker_list"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' creato.")
        return r


class LeadShakerBrokerUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                                 EmailVerifiedRequiredMixin, AdminOnlyMixin,
                                 UpdateView):
    model = LeadShakerBroker
    form_class = LeadShakerBrokerForm
    template_name = "tracking/leadshaker_form.html"
    success_url = reverse_lazy("tracking:broker_list")
    breadcrumb_parent = "tracking:broker_list"

    def get_breadcrumb_title(self) -> str:
        return f"Modifica {self.object.name}"

    def form_valid(self, form):
        r = super().form_valid(form)
        messages.success(self.request, f"Broker '{self.object.name}' aggiornato.")
        return r


class LeadShakerBrokerDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                                 AdminOnlyMixin, View):
    def post(self, request, pk):
        b = get_object_or_404(LeadShakerBroker, pk=pk)
        name = b.name
        b.delete()
        messages.success(request, f"Broker '{name}' eliminato.")
        return redirect("tracking:broker_list")


class LeadShakerBrokerSyncView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               AdminOnlyMixin, View):
    """Pull stati per un broker Lead-Shaker (solo Super Admin)."""

    def post(self, request, pk):
        broker = get_object_or_404(LeadShakerBroker, pk=pk)
        try:
            res = sync_mod.sync_leadshaker(broker)
            messages.success(
                request,
                f"Sync {broker.name}: {res['updated']} aggiornati "
                f"({res['matched']} agganciati su {res['seen']} righe).")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Sync {broker.name} errore: {exc}")
        return redirect("tracking:broker_list")


class LeadRerouteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                      MarketerOrAdminMixin, View):
    """Gira un lead a un altro broker (es. dopo un rifiuto): riassegna il
    broker selezionato e ri-esegue il push."""

    def post(self, request, pk):
        from django.contrib.contenttypes.models import ContentType
        lead = get_object_or_404(Lead, pk=pk)
        nxt = request.POST.get("next") or "tracking:lead_list"
        kind, _, bpk = (request.POST.get("broker") or "").partition(":")
        broker = broker_by_kind(kind, bpk) if bpk else None
        if broker is None:
            messages.error(request, "Seleziona un broker valido.")
            return redirect(nxt)
        lead.broker_content_type = ContentType.objects.get_for_model(type(broker))
        lead.broker_object_id = broker.pk
        lead.broker_lead_id = ""  # nuovo invio
        lead.save(update_fields=["broker_content_type", "broker_object_id",
                                 "broker_lead_id", "updated_at"])
        res = _do_push(lead, broker)
        if res.get("success"):
            messages.success(request, f"Lead girato a {broker.name}: accettato.")
        else:
            messages.error(request,
                           f"{broker.name} ha rifiutato: {res.get('error') or 'errore'}")
        return redirect(nxt)
