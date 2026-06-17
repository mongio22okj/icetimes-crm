import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.views import StaffRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_ERROR, LEVEL_SUCCESS, toast
from apps.core.tables import BulkAction, Column, Filter, TableConfig, TableView

from .forms import CampaignForm, LeadSourceForm
from .models import (
    AutoMessage,
    Campaign,
    DispatchLog,
    Lead,
    LeadSource,
    NotificationWebhook,
    Partner,
    TrackingLink,
)

from .sync import run_all_sources

logger = logging.getLogger(__name__)

# Pool per eseguire il ping-tree FUORI dalla request del postback: il broker
# che ci chiama deve ricevere subito la risposta, non aspettare i push HTTP
# verso gli altri broker (fino a ~30s ciascuno → rischio timeout lato loro).
_DISPATCH_POOL = ThreadPoolExecutor(max_workers=4,
                                    thread_name_prefix="postback-dispatch")


def _dispatch_async(lead_pk):
    """Esegue il dispatch ping-tree in un thread separato.

    Riceve il pk (non l'oggetto) e ri-carica il lead con una connessione DB
    propria del thread. Best-effort: qualsiasi errore viene loggato, mai
    propagato (la risposta al broker è già partita).
    """
    from django.db import close_old_connections
    close_old_connections()
    try:
        lead = Lead.objects.filter(pk=lead_pk).first()
        if lead is not None:
            from . import dispatch as _dispatch
            _dispatch.dispatch(lead)
    except Exception:  # noqa: BLE001
        logger.exception("Dispatch asincrono fallito per lead %s", lead_pk)
    finally:
        close_old_connections()


def _schedule_dispatch(lead_pk):
    """Lancia il dispatch async solo dopo il commit della transazione corrente.

    Con autocommit (nessun ATOMIC_REQUESTS) `on_commit` parte subito; se in
    futuro si abilitano le request atomiche, evita che il thread non trovi
    ancora il lead non committato."""
    from django.db import transaction
    transaction.on_commit(lambda: _DISPATCH_POOL.submit(_dispatch_async, lead_pk))


def _safe_next(request, default_name):
    """Ritorna il path `next` (relativo) se valido, altrimenti il default."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return reverse(default_name)


LEADS_TABLE = TableConfig(
    key="leads",
    columns=(
        Column("created_at", "Creato il", sortable=True, pinned=True,
               filter=Filter("daterange"),
               formatter=lambda v: v.strftime("%d/%m/%Y %H:%M") if v else ""),
        Column("is_deposit", "Depositare", sortable=True,
               formatter=lambda v: "✅ sì" if v else "—"),
        Column("firstname", "Nome", searchable=True),
        Column("lastname", "Cognome", searchable=True),
        Column("email", "Email", searchable=True),
        Column("phone", "Telefono", searchable=True),
        Column("ip", "IP", sortable=False),
        Column("country", "Paese",
               filter=Filter("select", choices=(
                   ("IT", "🇮🇹 Italia (IT)"),
                   ("ES", "🇪🇸 Spagna (ES)"),
                   ("DE", "🇩🇪 Germania (DE)"),
                   ("SE", "🇸🇪 Svezia (SE)"),
               ))),
        Column("status", "Stato", sortable=True,
               filter=Filter("text", placeholder="Filtra stato…"),
               template="leads/_table_cells.html#status"),
        Column("source", "Broker", sortable=True,
               filter=Filter("text", placeholder="Filtra broker…")),
        Column("event_at", "Aggiornato il", sortable=True,
               formatter=lambda v: v.strftime("%d/%m/%Y %H:%M") if v else "—"),
        Column("click_id", "ID cliccato", sortable=False,
               formatter=lambda v: v or "—"),
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
        ctx["country_options"] = [
            ("IT", "🇮🇹", "Italia"),
            ("ES", "🇪🇸", "Spagna"),
            ("DE", "🇩🇪", "Germania"),
            ("SE", "🇸🇪", "Svezia"),
        ]
        return ctx

    @staticmethod
    def _period_stats():
        """Counts + deposit conversion per period (doctorback-style panel)."""
        from datetime import timedelta

        from django.utils import timezone
        from django.utils.translation import gettext as _

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        periods = (
            ("Ieri", today - timedelta(days=1), today - timedelta(days=1)),
            ("Oggi", today, today),
            ("Settimana", week_start, today),
            ("La settimana scorsa", last_week_start, last_week_end),
            ("Mese", month_start, today),
            ("Il mese scorso", last_month_end.replace(day=1), last_month_end),
            ("Totale", None, None),
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

    # Priorità all'id-lead UNICO del broker (lead_id/uuid/…). Il click_id
    # è il codice del LINK (condiviso da tutti i lead di quel link), quindi
    # ambiguo: lo usiamo solo come ultima spiaggia.
    # NB: niente click_id qui. Il click_id è il codice del LINK, condiviso da
    # tutti i lead di quel link → usarlo come uniqueid collassa lead diversi
    # sulla stessa riga. Solo id-lead realmente univoci del broker.
    uniqueid = str(_first(data, "uniqueid", "lead_id", "leadId", "uuid",
                          "id", "customerId") or "")
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
        if lead is None:
            # Match anche per l'ID-lead broker salvato nel payload al push.
            lead = (Lead.objects.filter(payload__broker_lead_id=uniqueid)
                    .order_by("-created_at").first())
    if lead is None and email:
        lead = Lead.objects.filter(email__iexact=email).order_by("-created_at").first()
    if lead is None:
        # Nessun lead da agganciare. Crea una riga nuova SOLO se il postback
        # porta dati di contatto reali. Un postback di solo-stato (lead_id +
        # status, senza email/telefono/nome — o con placeholder template non
        # sostituiti) per un lead sconosciuto NON deve generare un orfano
        # vuoto: lo accettiamo e basta. Chiude il leak dei lead vuoti.
        has_contact = bool(email) or bool(_first(
            data, "phone", "phoneNumber", "fullphone",
            "firstname", "firstName", "first_name", "name",
            "lastname", "lastName", "last_name"))
        if not has_contact:
            return JsonResponse({
                "ok": True, "ignored": True,
                "reason": "status update for unknown lead, no contact data",
            })
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
    was_deposit_before = bool(lead.pk and lead.is_deposit)
    if status:
        lead.status = status[:120]
    # Deposito/FTD: o da un campo dedicato (ftd/deposit/…), o dallo stato
    # stesso quando vale "ftd"/"deposit" (IREV manda l'FTD come status=ftd).
    deposit_now = (deposit_raw is not None and _truthy(deposit_raw)) or _truthy(status)
    if deposit_now:
        lead.is_deposit = True
    if event_at:
        lead.event_at = event_at
    merged = dict(lead.payload or {})
    merged.update(data)
    lead.payload = merged

    # ── Duplicate detection — only when CREATING a new Lead row. ──────
    is_new_lead = lead.pk is None
    if is_new_lead and email:
        from datetime import timedelta

        from django.utils import timezone

        from .models import LeadSource as _LS
        match_kind = (lead.source or "").split("-", 1)[0]
        src = _LS.objects.filter(kind=match_kind).first() if match_kind else None
        window = src.duplicate_window_hours if src else 24
        if window:
            cutoff = timezone.now() - timedelta(hours=window)
            recent = Lead.objects.filter(
                email__iexact=email, created_at__gte=cutoff,
            ).exists()
            if recent:
                return JsonResponse({
                    "ok": True, "duplicate": True,
                    "reason": f"email seen within last {window}h",
                })

    # ── Lead scoring. ────────────────────────────────────────────────
    from .scoring import compute_score
    lead.score = compute_score(lead)

    lead.save()

    # ── Notifications (Slack/Discord/Telegram/generic). ──────────────
    from . import notifications
    base_payload = {
        "name": lead.full_name or "—",
        "email": lead.email,
        "phone": lead.phone,
        "country": lead.country,
        "source": lead.source,
        "score": lead.score,
    }
    try:
        if is_new_lead:
            notifications.fire("new_lead", base_payload)
        if deposit_now and not was_deposit_before:
            notifications.fire("ftd", {**base_payload, "broker": lead.source})
    except Exception:  # noqa: BLE001
        pass

    # ── Auto-email (speed-to-lead) — only on first creation. ─────────
    if is_new_lead:
        try:
            from . import auto_email
            auto_email.fire("new_lead", lead)
        except Exception:  # noqa: BLE001
            pass
    if deposit_now and not was_deposit_before:
        try:
            from . import auto_email
            auto_email.fire("ftd", lead)
        except Exception:  # noqa: BLE001
            pass

    # ── Auto-dispatch ping-tree if any active source has it on. ──────
    if is_new_lead:
        try:
            from .models import LeadSource as _LS
            if _LS.objects.filter(is_active=True, auto_dispatch=True).exists():
                # Non bloccare la risposta al broker: il ping-tree gira async.
                _schedule_dispatch(lead.pk)
        except Exception:  # noqa: BLE001
            pass

    # ── Sync Sale status when Lead comes from a product landing. ─────
    # uniqueid = "sale-<pk>" → update the corresponding Sale record.
    if lead.uniqueid and lead.uniqueid.startswith("sale-"):
        try:
            from django.utils import timezone as _tz
            from apps.products.models import Sale
            sale_pk = int(lead.uniqueid.split("-", 1)[1])
            sale = Sale.objects.filter(pk=sale_pk).first()
            if sale:
                if lead.is_deposit and sale.status != Sale.STATUS_SOLD:
                    sale.status = Sale.STATUS_SOLD
                    sale.sold_at = _tz.now()
                    sale.save(update_fields=["status", "sold_at", "updated_at"])
                elif lead.status.lower() in ("rejected", "invalid", "duplicate", "lost"):
                    if sale.status == Sale.STATUS_PENDING:
                        sale.status = Sale.STATUS_LOST
                        sale.save(update_fields=["status", "updated_at"])
                elif sale.status == Sale.STATUS_PENDING and lead.status:
                    sale.notes = f"Broker status: {lead.status}"
                    sale.save(update_fields=["notes", "updated_at"])
        except Exception:  # noqa: BLE001
            pass

    return JsonResponse({"ok": True, "id": lead.pk, "score": lead.score})


# ── Broker dashboard ────────────────────────────────────────────────────

class BrokersDashboardView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           TemplateView):
    """Card grid of every configured LeadSource with real-data metrics.

    For each LeadSource we compute: total leads, FTD count, conversion
    rate, last activity timestamp. Matching uses the Lead.source field
    which carries the source slug (`kind-pk` for DB rows, `kind` for env
    shims). Replaces the deleted "API Broker" page with a metrics-focused
    overview rather than a send form.
    """
    template_name = "leads/brokers_dashboard.html"
    breadcrumb_title = "Broker"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Max, Q, Sum

        ctx = super().get_context_data(**kwargs)
        sources = list(LeadSource.objects.all())

        # One pass: aggregate counts grouped by Lead.source so the page is
        # cheap even with many brokers.
        per_source = {
            row["source"]: row for row in
            Lead.objects.values("source").annotate(
                leads=Count("id"),
                ftd=Count("id", filter=Q(is_deposit=True)),
                last=Max("created_at"),
            )
        }

        cards = []
        total_leads = total_ftd = 0
        total_revenue = 0
        for s in sources:
            # Match leads whose Lead.source equals slug or starts with kind.
            matched = [
                v for k, v in per_source.items()
                if k == s.slug or k.startswith(f"{s.kind}-") or k == s.kind
            ]
            leads = sum(m["leads"] for m in matched)
            ftd = sum(m["ftd"] for m in matched)
            last = max((m["last"] for m in matched if m["last"]), default=None)
            conv = (ftd * 100 / leads) if leads else 0
            revenue = float(s.payout_per_ftd or 0) * ftd + float(s.payout_per_lead or 0) * leads
            total_leads += leads
            total_ftd += ftd
            total_revenue += revenue
            cards.append({
                "source": s,
                "leads": leads,
                "ftd": ftd,
                "conv": conv,
                "last": last,
                "revenue": revenue,
            })
        cards.sort(key=lambda c: c["revenue"], reverse=True)

        ctx["cards"] = cards
        ctx["totals"] = {
            "leads": total_leads,
            "ftd": total_ftd,
            "revenue": total_revenue,
            "conv": (total_ftd * 100 / total_leads) if total_leads else 0,
            "brokers_active": sum(1 for s in sources if s.is_active),
            "brokers_total": len(sources),
        }
        return ctx


# ── Campaign CRUD ────────────────────────────────────────────────────────

class CampaignListView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, StaffRequiredMixin,
                       TemplateView):
    template_name = "leads/campaign_list.html"
    breadcrumb_title = "Campagne"

    def get_context_data(self, **kwargs):
        from decimal import Decimal
        ctx = super().get_context_data(**kwargs)
        campaigns = list(Campaign.objects.all())
        ctx["campaigns"] = campaigns
        totals = {
            "budget": sum((c.budget for c in campaigns), Decimal("0")),
            "spent": sum((c.spent for c in campaigns), Decimal("0")),
            "leads": sum(c.leads_count for c in campaigns),
            "clicks": sum(c.clicks for c in campaigns),
            "active": sum(1 for c in campaigns if c.status == Campaign.STATUS_ACTIVE),
            "total": len(campaigns),
        }
        totals["cpa"] = (totals["spent"] / totals["leads"]) if totals["leads"] else None
        ctx["totals"] = totals
        return ctx


class CampaignCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         CreateView):
    model = Campaign
    form_class = CampaignForm
    template_name = "leads/campaign_form.html"
    success_url = reverse_lazy("leads:campaign_list")
    breadcrumb_title = "Nuova campagna"
    breadcrumb_parent = ("Campagne", "leads:campaign_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Campagna '{self.object.name}' creata.")
        return response


class CampaignUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         UpdateView):
    model = Campaign
    form_class = CampaignForm
    template_name = "leads/campaign_form.html"
    success_url = reverse_lazy("leads:campaign_list")
    breadcrumb_title = "Modifica campagna"
    breadcrumb_parent = ("Campagne", "leads:campaign_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Campagna '{self.object.name}' aggiornata.")
        return response


class CampaignDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                         StaffRequiredMixin, View):
    def post(self, request, pk):
        campaign = Campaign.objects.filter(pk=pk).first()
        if campaign is None:
            toast(request, LEVEL_ERROR, "Campagna non trovata.")
            return redirect("leads:campaign_list")
        name = campaign.name
        campaign.delete()
        toast(request, LEVEL_SUCCESS, f"Campagna '{name}' eliminata.")
        return redirect("leads:campaign_list")


# ── Lead Source (broker API) CRUD ────────────────────────────────────────

class LeadSourceListView(BreadcrumbsMixin, LoginRequiredMixin,
                         EmailVerifiedRequiredMixin, StaffRequiredMixin,
                         TemplateView):
    template_name = "leads/leadsource_list.html"
    breadcrumb_title = "Broker"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = LeadSource.objects.all()

        # ── Filters (admin-style sidebar) ──────────────────────────────
        kind = self.request.GET.get("kind") or ""
        active = self.request.GET.get("active") or ""
        if kind:
            qs = qs.filter(kind=kind)
        if active == "yes":
            qs = qs.filter(is_active=True)
        elif active == "no":
            qs = qs.filter(is_active=False)

        sources = list(qs)
        ctx["sources"] = sources
        ctx["kind_choices"] = LeadSource.KIND_CHOICES
        ctx["active_filter"] = active
        ctx["kind_filter"] = kind
        # Totals computed over the unfiltered set so the cards stay stable.
        all_sources = list(LeadSource.objects.all())
        ctx["totals"] = {
            "total": len(all_sources),
            "active": sum(1 for s in all_sources if s.is_active),
            "with_api": sum(1 for s in all_sources if s.kind),
        }
        # Postback endpoint principale da dare ai broker (token reale).
        from django.urls import reverse
        token = settings.LEADS_POSTBACK_TOKEN
        base = self.request.build_absolute_uri(reverse("leads:postback"))
        ctx["postback_url"] = f"{base}?token={token}" if token else ""
        ctx["postback_configured"] = bool(token)
        # Heartbeat del poller speed-to-lead (sync automatica).
        from apps.leads.poller import get_heartbeat
        ctx["poller"] = get_heartbeat()
        return ctx


class LeadSourceBulkDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               StaffRequiredMixin, View):
    def post(self, request):
        pks = request.POST.getlist("selected")
        if not pks:
            toast(request, LEVEL_ERROR, "Nessun broker selezionato.")
            return redirect("leads:source_list")
        qs = LeadSource.objects.filter(pk__in=pks)
        count = qs.count()
        qs.delete()
        toast(request, LEVEL_SUCCESS,
              f"{count} broker eliminat{'o' if count == 1 else 'i'}.")
        return redirect("leads:source_list")


class TrackBoxView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin,
                   TemplateView):
    """Tabella di riferimento dei tipi di integrazione broker."""
    template_name = "leads/trackbox.html"
    breadcrumb_title = "TrackBox"

    def get_context_data(self, **kwargs):
        from django.db.models import Count, Q
        ctx = super().get_context_data(**kwargs)
        # Conteggi per tipo (broker totali e attivi) in una sola query.
        counts = {
            row["kind"]: row
            for row in LeadSource.objects.values("kind").annotate(
                total=Count("id"),
                active=Count("id", filter=Q(is_active=True)),
            )
        }
        rows = []
        for code, label in LeadSource.KIND_CHOICES:
            c = counts.get(code, {})
            rows.append({
                "code": code,
                "label": label,
                "total": c.get("total", 0),
                "active": c.get("active", 0),
            })
        ctx["rows"] = rows
        return ctx


class TrackingLinkListView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           CreateView):
    """Lista + creazione dei link corti di tracciamento."""
    model = TrackingLink
    template_name = "leads/tracking_links.html"
    breadcrumb_title = "Link tracciamento"

    def get_form_class(self):
        from .forms import TrackingLinkForm
        return TrackingLinkForm

    def get_success_url(self):
        return _safe_next(self.request, "leads:tracking_links")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Link creato: /t/{self.object.code}")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["links"] = list(TrackingLink.objects.select_related("source").all())
        ctx["brokers"] = list(LeadSource.objects.order_by("name"))
        ctx["base_url"] = self.request.build_absolute_uri("/").rstrip("/")
        return ctx


class TrackingLinkUpdateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    """Salvataggio inline di un link dalla tabella editabile."""

    def post(self, request, pk):
        link = get_object_or_404(TrackingLink, pk=pk)
        link.name = (request.POST.get("name") or "").strip()[:120]
        link.destination = (request.POST.get("destination") or "").strip()
        sid = request.POST.get("source") or ""
        link.source_id = int(sid) if sid.isdigit() else None
        link.is_active = request.POST.get("is_active") == "on"
        if not link.destination:
            toast(request, LEVEL_ERROR, "La destinazione non può essere vuota.")
        else:
            link.save()
            toast(request, LEVEL_SUCCESS, f"Link /t/{link.code} aggiornato.")
        return redirect(_safe_next(request, "leads:tracking_links"))


class TrackingLinkDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    def post(self, request, pk):
        from .models import TrackingLink
        TrackingLink.objects.filter(pk=pk).delete()
        toast(request, LEVEL_SUCCESS, "Link eliminato.")
        return redirect(_safe_next(request, "leads:tracking_links"))


# ── Visualizzatori: pannello centrale di approvazione ────────────────────
def _viewer_queryset():
    """Solo account visualizzatore (gruppo Viewers, non staff)."""
    from django.contrib.auth import get_user_model
    from .viewer import viewer_group
    User = get_user_model()
    return User.objects.filter(groups=viewer_group(), is_staff=False)


class ViewerRequestListView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            TemplateView):
    template_name = "leads/viewer_requests.html"
    breadcrumb_title = "Visualizzatori"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        viewers = list(_viewer_queryset().order_by("-date_joined"))
        ctx["pending"] = [u for u in viewers if not u.is_active]
        ctx["active"] = [u for u in viewers if u.is_active]
        return ctx


class ViewerApproveView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                        StaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(_viewer_queryset(), pk=pk)
        user.is_active = True
        user.save(update_fields=["is_active"])
        toast(request, LEVEL_SUCCESS, f"Accesso approvato per '{user.username}'.")
        return redirect("leads:viewer_requests")


class ViewerRevokeView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                       StaffRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(_viewer_queryset(), pk=pk)
        username = user.username
        user.delete()
        toast(request, LEVEL_SUCCESS, f"Accesso rimosso per '{username}'.")
        return redirect("leads:viewer_requests")


class LeadSourceCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           CreateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/leadsource_form.html"
    success_url = reverse_lazy("leads:source_list")
    breadcrumb_title = "Nuovo broker"
    breadcrumb_parent = ("Broker", "leads:source_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Broker '{self.object.name}' creato.")
        return response


class LeadSourceUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           UpdateView):
    model = LeadSource
    form_class = LeadSourceForm
    template_name = "leads/leadsource_form.html"
    success_url = reverse_lazy("leads:source_list")
    breadcrumb_title = "Modifica broker"
    breadcrumb_parent = ("Broker", "leads:source_list")

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Broker '{self.object.name}' aggiornato.")
        return response


class LeadSourceDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    def post(self, request, pk):
        source = LeadSource.objects.filter(pk=pk).first()
        if source is None:
            toast(request, LEVEL_ERROR, "Broker non trovato.")
            return redirect("leads:source_list")
        name = source.name
        source.delete()
        toast(request, LEVEL_SUCCESS, f"Broker '{name}' eliminato.")
        return redirect("leads:source_list")


# ── Broker landing pages management ──────────────────────────────────────

class BrokerLandingListView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            TemplateView):
    template_name = "leads/landing_list.html"
    breadcrumb_title = "Landing"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sources = list(LeadSource.objects.all())
        ctx["sources"] = sources
        ctx["totals"] = {
            "total": len(sources),
            "published": sum(1 for s in sources if s.landing_active and s.landing_slug),
        }
        return ctx


# ── Reports (ROI per broker + CPA per campaign) ─────────────────────────

class ReportsView(BreadcrumbsMixin, LoginRequiredMixin,
                  EmailVerifiedRequiredMixin, StaffRequiredMixin,
                  TemplateView):
    """ROI line chart per broker + CPA bar chart per campaign."""
    template_name = "leads/reports.html"
    breadcrumb_title = "Report"

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        from django.db.models import Count, Q
        from django.utils import timezone

        ctx = super().get_context_data(**kwargs)

        # ── ROI per broker: FTD count per day per broker, last 30 days ──
        today = timezone.localdate()
        days = [today - timedelta(days=i) for i in range(29, -1, -1)]
        labels = [d.strftime("%d/%m") for d in days]
        sources = list(LeadSource.objects.filter(is_active=True))
        datasets = []
        palette = ["#6366f1", "#06b6d4", "#10b981", "#f59e0b",
                   "#ef4444", "#8b5cf6", "#ec4899", "#84cc16"]
        for i, s in enumerate(sources[:8]):
            per_day = (
                Lead.objects
                .filter(source__startswith=s.kind, is_deposit=True,
                        created_at__date__gte=days[0])
                .extra(select={"d": "DATE(created_at)"})
                .values("d")
                .annotate(n=Count("id"))
            )
            counts_by_day = {row["d"]: row["n"] for row in per_day}
            datasets.append({
                "label": s.name,
                "data": [counts_by_day.get(d, 0) for d in days],
                "borderColor": palette[i % len(palette)],
                "backgroundColor": "transparent",
                "tension": 0.35,
            })
        roi_chart = {"labels": labels, "datasets": datasets}

        # ── CPA per campaign: bar chart ─────────────────────────────────
        campaigns = Campaign.objects.all()
        cpa_chart = {
            "labels": [c.name for c in campaigns],
            "data": [float(c.cpa) if c.cpa is not None else 0 for c in campaigns],
            "platforms": [c.get_platform_display() for c in campaigns],
        }

        ctx["roi_chart_json"] = json.dumps(roi_chart)
        ctx["cpa_chart_json"] = json.dumps(cpa_chart)
        ctx["has_brokers"] = bool(sources)
        ctx["has_campaigns"] = campaigns.exists()
        return ctx


# ── NotificationWebhook CRUD ────────────────────────────────────────────

class NotificationListView(BreadcrumbsMixin, LoginRequiredMixin,
                           EmailVerifiedRequiredMixin, StaffRequiredMixin,
                           ListView):
    model = NotificationWebhook
    template_name = "leads/notification_list.html"
    context_object_name = "hooks"
    breadcrumb_title = "Notifiche"


class NotificationCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             CreateView):
    model = NotificationWebhook
    template_name = "leads/notification_form.html"
    success_url = reverse_lazy("leads:notification_list")
    breadcrumb_title = "Nuovo webhook"
    breadcrumb_parent = ("Notifiche", "leads:notification_list")

    def get_form_class(self):
        from .forms import NotificationWebhookForm
        return NotificationWebhookForm

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Webhook '{self.object.name}' creato.")
        return response


class NotificationUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                             EmailVerifiedRequiredMixin, StaffRequiredMixin,
                             UpdateView):
    model = NotificationWebhook
    template_name = "leads/notification_form.html"
    success_url = reverse_lazy("leads:notification_list")
    breadcrumb_title = "Modifica webhook"
    breadcrumb_parent = ("Notifiche", "leads:notification_list")

    def get_form_class(self):
        from .forms import NotificationWebhookForm
        return NotificationWebhookForm


class NotificationDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                             StaffRequiredMixin, View):
    def post(self, request, pk):
        NotificationWebhook.objects.filter(pk=pk).delete()
        toast(request, LEVEL_SUCCESS, "Webhook eliminato.")
        return redirect("leads:notification_list")


class NotificationTestView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    """Fire a fake "test" event to verify the hook is configured right."""

    def post(self, request, pk):
        from . import notifications as _n
        hook = NotificationWebhook.objects.filter(pk=pk).first()
        if hook is None:
            toast(request, LEVEL_ERROR, "Webhook non trovato.")
            return redirect("leads:notification_list")
        ok, info = _n.send_to_webhook(hook, "new_lead", {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+393331234567",
            "country": "IT",
            "source": "test",
            "score": 75,
        })
        if ok:
            toast(request, LEVEL_SUCCESS, f"Test inviato a '{hook.name}' — {info}")
        else:
            toast(request, LEVEL_ERROR, f"Test fallito — {info}")
        return redirect("leads:notification_list")


# ── AutoMessage CRUD ────────────────────────────────────────────────────

class AutoMessageListView(BreadcrumbsMixin, LoginRequiredMixin,
                          EmailVerifiedRequiredMixin, StaffRequiredMixin,
                          ListView):
    model = AutoMessage
    template_name = "leads/auto_message_list.html"
    context_object_name = "messages_list"
    breadcrumb_title = "Auto-email"


class AutoMessageCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            CreateView):
    model = AutoMessage
    template_name = "leads/auto_message_form.html"
    success_url = reverse_lazy("leads:auto_message_list")
    breadcrumb_title = "Nuova auto-email"
    breadcrumb_parent = ("Auto-email", "leads:auto_message_list")

    def get_form_class(self):
        from .forms import AutoMessageForm
        return AutoMessageForm


class AutoMessageUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            UpdateView):
    model = AutoMessage
    template_name = "leads/auto_message_form.html"
    success_url = reverse_lazy("leads:auto_message_list")
    breadcrumb_title = "Modifica auto-email"
    breadcrumb_parent = ("Auto-email", "leads:auto_message_list")

    def get_form_class(self):
        from .forms import AutoMessageForm
        return AutoMessageForm


class AutoMessageDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            StaffRequiredMixin, View):
    def post(self, request, pk):
        AutoMessage.objects.filter(pk=pk).delete()
        toast(request, LEVEL_SUCCESS, "Auto-email eliminata.")
        return redirect("leads:auto_message_list")


# ── Ping-tree dispatch ──────────────────────────────────────────────────

class DispatchLogView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, StaffRequiredMixin,
                      ListView):
    model = DispatchLog
    template_name = "leads/dispatch_log.html"
    context_object_name = "logs"
    paginate_by = 50
    breadcrumb_title = "Dispatch log"

    def get_queryset(self):
        return DispatchLog.objects.select_related("lead", "source")

    def get_context_data(self, **kwargs):
        from django.db.models import Avg, Count, Q
        ctx = super().get_context_data(**kwargs)
        per_broker = (
            DispatchLog.objects
            .values("source_name")
            .annotate(
                total=Count("id"),
                success=Count("id", filter=Q(success=True)),
                avg_latency=Avg("latency_ms"),
            )
            .order_by("-total")
        )
        for row in per_broker:
            row["rate"] = (row["success"] * 100 / row["total"]) if row["total"] else 0
        ctx["per_broker"] = per_broker
        return ctx


class LeadDispatchTriggerView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                              StaffRequiredMixin, View):
    """Manually fire ping-tree dispatch for a single Lead."""

    def post(self, request, pk):
        lead = Lead.objects.filter(pk=pk).first()
        if lead is None:
            toast(request, LEVEL_ERROR, "Lead non trovato.")
            return redirect("leads:list")
        from . import dispatch as _d
        attempts = _d.dispatch(lead)
        ok_count = sum(1 for a in attempts if a["success"])
        if ok_count:
            toast(request, LEVEL_SUCCESS,
                  f"Dispatch lead #{lead.pk}: {ok_count}/{len(attempts)} broker hanno accettato.")
        elif attempts:
            toast(request, LEVEL_ERROR,
                  f"Dispatch lead #{lead.pk}: nessun broker ha accettato ({len(attempts)} tentativi).")
        else:
            toast(request, LEVEL_ERROR,
                  "Nessun broker push-capable attivo da provare.")
        return redirect("leads:dispatch_log")


# ── Public broker landing /b/<slug>/ ────────────────────────────────────

class BrokerLandingView(TemplateView):
    """Public landing for a single broker. Form posts to BrokerLandingSubmit."""
    template_name = "leads/broker_landing.html"

    def get_context_data(self, **kwargs):
        from django.http import Http404
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        broker = LeadSource.objects.filter(
            landing_slug=slug, landing_active=True, is_active=True,
        ).first()
        if broker is None:
            raise Http404()
        ctx["broker"] = broker
        return ctx


@method_decorator(csrf_exempt, name="dispatch")
class BrokerLandingSubmitView(View):
    """Form submit endpoint for a broker landing.

    Creates a Lead tagged to the broker source, then force-dispatches
    the lead to that broker only (not ping-tree). Fires notifications
    and auto-email per the global config.
    """

    def post(self, request, slug):
        from django.http import Http404, JsonResponse
        from . import dispatch as _dispatch
        from . import notifications as _notifications
        from .scoring import compute_score

        broker = LeadSource.objects.filter(
            landing_slug=slug, landing_active=True, is_active=True,
        ).first()
        if broker is None:
            raise Http404()

        data = request.POST
        email = (data.get("email") or "").strip()
        if not email:
            return JsonResponse({"ok": False, "error": "email required"}, status=400)

        import secrets
        import time
        uniqueid = f"land-{broker.slug}-{int(time.time())}-{secrets.token_hex(3)}"
        payload = {k: v for k, v in data.items() if k != "csrfmiddlewaretoken"}
        # IP reale del visitatore (dietro Cloudflare → nginx). IREV lo richiede.
        real_ip = (request.META.get("HTTP_CF_CONNECTING_IP")
                   or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                   or request.META.get("REMOTE_ADDR", ""))
        if real_ip:
            payload.setdefault("ip", real_ip)

        lead = Lead.objects.create(
            uniqueid=uniqueid,
            firstname=(data.get("firstname") or data.get("nome") or "").strip()[:120],
            lastname=(data.get("lastname") or data.get("cognome") or "").strip()[:120],
            email=email[:254],
            phone=(data.get("phone") or data.get("telefono")
                   or data.get("tel") or data.get("full_phone") or "").strip()[:32],
            country=(data.get("country") or data.get("iso") or "IT").strip().upper()[:8],
            status="lead",
            source=broker.slug,
            payload=payload,
        )
        lead.score = compute_score(lead)
        lead.save(update_fields=["score"])

        # Force-dispatch to THIS broker only.
        try:
            _dispatch.dispatch(lead, sources=[broker])
        except Exception:  # noqa: BLE001
            pass

        # Auto-login: se il broker ha risposto con un auto_login_url, mandiamo
        # la persona dritta sulla sua piattaforma (massima conversione).
        auto_login = ""
        _dl = (DispatchLog.objects.filter(lead=lead, source=broker, success=True)
               .order_by("-id").first())
        if _dl and isinstance(_dl.response, dict):
            auto_login = (_dl.response.get("auto_login_url")
                          or _dl.response.get("autoLoginUrl")
                          or _dl.response.get("redirect_url") or "")
            # Memorizza l'ID-lead lato broker: il loro postback lo rimanda,
            # così agganciamo l'aggiornamento di stato al lead esatto.
            broker_lead_id = (_dl.response.get("lead_uuid")
                              or _dl.response.get("lead_id")
                              or _dl.response.get("id"))
            if broker_lead_id:
                lead.uniqueid = str(broker_lead_id)[:128]
                lead.payload = {**(lead.payload or {}),
                                "broker_lead_id": str(broker_lead_id)}
                lead.save(update_fields=["uniqueid", "payload"])

        # Notifications (silent fail).
        try:
            _notifications.fire("new_lead", {
                "name": lead.full_name or "—",
                "email": lead.email,
                "phone": lead.phone,
                "country": lead.country,
                "source": broker.name,
                "score": lead.score,
            })
        except Exception:  # noqa: BLE001
            pass

        # Auto-email.
        try:
            from . import auto_email
            auto_email.fire("new_lead", lead)
        except Exception:  # noqa: BLE001
            pass

        # POST nativo del form (es. funnel statica self-hostata): il browser
        # si aspetta una navigazione, non JSON → reindirizziamo direttamente.
        # Le nostre landing in fetch (Accept */*) ricevono invece il JSON.
        target = auto_login or broker.landing_redirect_url or ""
        if "text/html" in request.headers.get("Accept", ""):
            if target:
                from django.http import HttpResponseRedirect
                return HttpResponseRedirect(target)
            # Nessun auto-login: mostra una pagina di conferma (non rimandare
            # il visitatore su "/" che è dietro il gate).
            from django.http import HttpResponse
            msg = broker.landing_success_message or "Registrazione completata!"
            return HttpResponse(
                "<!doctype html><meta charset=utf-8>"
                "<div style='font-family:system-ui;text-align:center;padding:64px'>"
                f"<h2>✅ {msg}</h2></div>")

        return JsonResponse({
            "ok": True,
            "lead_id": lead.pk,
            "redirect": target,
        })


# ── Per-partner inbound postback /in/<slug>/ ────────────────────────────

@csrf_exempt
def partner_postback(request, slug):
    """Inbound postback endpoint for a single Partner.

    Authentication: ?token=<partner.webhook_token> OR X-Postback-Token
    header. Lead is created with source=partner-<slug> so attribution is
    automatic. Fires the full pipeline (scoring, notifications, auto-
    email, auto-dispatch) just like the main /leads/postback/.
    """
    partner = Partner.objects.filter(slug=slug, is_active=True).first()
    if partner is None:
        return JsonResponse({"ok": False, "error": "partner not found"}, status=404)

    supplied = request.GET.get("token") or request.headers.get("X-Postback-Token", "")
    if not partner.webhook_token or not hmac.compare_digest(supplied, partner.webhook_token):
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

    # Priorità all'id-lead UNICO del broker (lead_id/uuid/…). Il click_id
    # è il codice del LINK (condiviso da tutti i lead di quel link), quindi
    # ambiguo: lo usiamo solo come ultima spiaggia.
    # NB: niente click_id qui. Il click_id è il codice del LINK, condiviso da
    # tutti i lead di quel link → usarlo come uniqueid collassa lead diversi
    # sulla stessa riga. Solo id-lead realmente univoci del broker.
    uniqueid = str(_first(data, "uniqueid", "lead_id", "leadId", "uuid",
                          "id", "customerId") or "")
    email = str(_first(data, "email") or "")
    if not email and not uniqueid:
        return JsonResponse({"ok": False, "error": "email or uniqueid required"}, status=400)

    import secrets
    import time
    if not uniqueid:
        uniqueid = f"partner-{slug}-{int(time.time())}-{secrets.token_hex(3)}"

    # Dedup: same email from same partner within 24h is a no-op.
    if email:
        from datetime import timedelta

        from django.utils import timezone
        cutoff = timezone.now() - timedelta(hours=24)
        recent = Lead.objects.filter(
            email__iexact=email,
            source=f"partner-{slug}",
            created_at__gte=cutoff,
        ).first()
        if recent is not None:
            return JsonResponse({
                "ok": True, "duplicate": True, "id": recent.pk,
                "reason": "same email from this partner within 24h",
            })

    lead = Lead(source=f"partner-{slug}", uniqueid=uniqueid)
    if email:
        lead.email = email
    for field, keys in (
        ("firstname", ("firstname", "firstName", "first_name", "name")),
        ("lastname", ("lastname", "lastName", "last_name")),
        ("phone", ("phone", "phoneNumber", "fullphone")),
        ("country", ("country", "countryCode", "geo")),
        ("status", ("status", "callStatus", "saleStatus")),
    ):
        value = _first(data, *keys)
        if value:
            setattr(lead, field, str(value)[:120])

    deposit_raw = _first(data, "isDeposit", "deposit", "ftd", "hasFTD")
    if deposit_raw is not None and _truthy(deposit_raw):
        lead.is_deposit = True

    lead.payload = data

    # Scoring + save.
    from .scoring import compute_score
    lead.score = compute_score(lead)
    lead.save()

    # Pipeline: notifications + auto-email + auto-dispatch (silent fail).
    try:
        from . import notifications
        notifications.fire("new_lead", {
            "name": lead.full_name or "—",
            "email": lead.email, "phone": lead.phone,
            "country": lead.country, "source": partner.name,
            "score": lead.score,
        })
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import auto_email
        auto_email.fire("new_lead", lead)
    except Exception:  # noqa: BLE001
        pass
    try:
        if LeadSource.objects.filter(is_active=True, auto_dispatch=True).exists():
            # Postback partner: dispatch async, risposta immediata al caller.
            _schedule_dispatch(lead.pk)
    except Exception:  # noqa: BLE001
        pass

    return JsonResponse({"ok": True, "id": lead.pk, "score": lead.score})
