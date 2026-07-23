import json
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.orders.models import Order

User = get_user_model()


# Ciambella "Lead per stato": ogni broker scrive lo status in modo diverso
# (NO ANSWER / NOANSWER / No Answer …). Li accorpiamo in un set fisso di
# stati canonici, ognuno con un colore dedicato (niente più doppioni né
# colori ripetuti). Ordine = ordine di visualizzazione nella legenda.
STATUS_BUCKETS = [
    # (key,            label,           color)
    ("new",           "New",           "#2563eb"),  # blu
    ("no_answer",     "No Answer",     "#d97706"),  # ambra
    ("low_potential", "Low Potential", "#92400e"),  # marrone
    ("instant_call",  "Instant Call",  "#0891b2"),  # ciano
    ("work",          "Work",          "#0d9488"),  # verde acqua
    ("callback",      "Callback",      "#eab308"),  # giallo
    ("no_interest",   "No Interest",   "#7c3aed"),  # viola
    ("no_money",      "No Money",      "#dc2626"),  # rosso
    ("wrong_number",  "Wrong Number",  "#6b7280"),  # grigio
    ("ftd",           "FTD",           "#16a34a"),  # verde
    ("other",         "Altro",         "#94a3b8"),  # grigio chiaro
]

# Chiave normalizzata (solo a-z0-9) → bucket canonico.
_STATUS_SYNONYMS = {
    "new": "new", "newlead": "new", "nuovo": "new", "fresh": "new", "lead": "new",
    "noanswer": "no_answer", "busynoresponse": "no_answer", "busy": "no_answer",
    "noresponse": "no_answer", "na": "no_answer", "noanswered": "no_answer",
    "lowpotential": "low_potential", "notpotential": "low_potential",
    "lowpot": "low_potential", "lowquality": "low_potential",
    "instantcall": "instant_call", "instant": "instant_call", "autocall": "instant_call",
    "work": "work", "working": "work", "inwork": "work", "underwork": "work",
    "callback": "callback", "recall": "callback", "calllater": "callback",
    "callbacklater": "callback",
    "nointerest": "no_interest", "notinterested": "no_interest",
    "notinterest": "no_interest", "ni": "no_interest",
    "nomoney": "no_money", "nofunds": "no_money", "nobudget": "no_money",
    "wrongnumber": "wrong_number", "wrongdetails": "wrong_number",
    "wronginfo": "wrong_number", "invalidnumber": "wrong_number",
    "wrongdata": "wrong_number",
    "ftd": "ftd", "deposit": "ftd", "deposited": "ftd", "depositor": "ftd",
}


def status_bucket(raw):
    """Normalizza lo status grezzo del broker in uno dei bucket canonici."""
    key = re.sub(r"[^a-z0-9]", "", (raw or "").lower())
    if not key:
        return "new"  # status vuoto = lead nuovo, non ancora lavorato
    return _STATUS_SYNONYMS.get(key, "other")


class DashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        from apps.tracking.models import Lead, all_brokers
        from django.utils import timezone

        # Escludiamo i duplicati (is_duplicate) E i lead di TEST ("test" in
        # nome/cognome/email o status "Test") da TUTTI i conteggi/statistiche.
        # Restano visibili solo nella pagina Lead (riga rossa).
        from django.db.models import Q as _Q
        _test_q = (_Q(firstname__icontains="test") | _Q(lastname__icontains="test")
                   | _Q(email__icontains="test") | _Q(status__iexact="test"))
        # Contano SOLO i lead VALIDI: consegnati al broker (hanno l'auto-login).
        # Errori di push, duplicati e test restano fuori da tutti i numeri.
        leads = (Lead.objects.filter(is_duplicate=False)
                 .filter(payload__has_key="login_url").exclude(_test_q))
        total = leads.count()
        ftd = leads.filter(is_deposit=True).count()
        conv = round(ftd * 100 / total, 1) if total else 0
        leads_today = leads.filter(created_at__date=timezone.localdate()).count()
        brokers = all_brokers()
        brokers_active = sum(1 for b in brokers if b.is_active)

        kpis = [
            {"label": "Lead totali", "value": total, "icon": "target", "accent": "#6366f1"},
            {"label": "FTD", "value": ftd, "icon": "dollar-sign", "accent": "#16a34a"},
            {"label": "Conversione", "value": f"{conv}%", "icon": "trending-up", "accent": "#0891b2"},
            {"label": "Broker attivi", "value": brokers_active, "icon": "plug", "accent": "#d97706"},
        ]
        by_broker = []
        for b in sorted(brokers, key=lambda x: x.name.lower()):
            bl = (Lead.for_broker(b).filter(is_duplicate=False)
                  .filter(payload__has_key="login_url").exclude(_test_q))
            by_broker.append({"name": b.name, "leads": bl.count(),
                              "ftd": bl.filter(is_deposit=True).count()})
        recent_leads = list(leads.order_by("-created_at")[:10])
        _badge_colors = {k: c for k, _lbl, c in STATUS_BUCKETS}
        for _l in recent_leads:
            _l.badge_color = _badge_colors["ftd"] if _l.is_deposit else _badge_colors.get(status_bucket(_l.status), "#94a3b8")
        return render(request, "dashboard/index.html", {
            "kpis": kpis,
            "by_broker": by_broker,
            "recent_leads": recent_leads,
            "leads_today": leads_today,
            "breadcrumbs": [("Dashboard", None)],
        })


class ChartsShowcaseView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    """Gallery rendering 8 ApexCharts variants with sample data."""

    def get(self, request):
        return render(request, "dashboard/charts_showcase.html", {
            "breadcrumbs": [("Dashboard", "/"), ("Charts", None)],
        })


# ── Dashboard variants ──────────────────────────────────────────────────
# Each variant ships with realistic mock data matching the Laravel/Next
# siblings. Stats, chart payloads, and tables are all pre-baked here so
# the templates stay declarative.

def _stat(label, value, delta, trend, icon, accent, spark):
    return {
        "label": label, "value": value, "delta": delta, "trend": trend,
        "icon": icon, "accent": accent, "spark": json.dumps(spark),
    }


class AnalyticsDashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        stats = [
            _stat("Page Views", "284,392", "+24.7%", "up", "eye", "#16a34a",
                  [120, 132, 128, 145, 160, 158, 175, 190, 210, 225, 248, 284]),
            _stat("Unique Visitors", "42,847", "+12.3%", "up", "users", "#0891b2",
                  [22, 25, 24, 28, 31, 30, 33, 35, 38, 40, 41, 43]),
            _stat("Bounce Rate", "32.4%", "-5.2%", "up", "mouse-pointer", "#6366f1",
                  [42, 40, 39, 38, 37, 36, 35, 34, 34, 33, 33, 32]),
            _stat("Avg. Session", "4m 32s", "+8.1%", "up", "clock", "#d97706",
                  [3.2, 3.4, 3.5, 3.7, 3.8, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.5]),
        ]
        page_views = {
            "categories": ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                           "Oct", "Nov", "Dec", "Jan", "Feb"],
            "views": [158000, 167000, 174000, 183000, 195000, 208000,
                      221000, 235000, 247000, 262000, 271000, 284392],
            "visitors": [21000, 23000, 24800, 26500, 28800, 31000,
                         33500, 35800, 38000, 40500, 41600, 42847],
        }
        category_revenue = [
            {"category": "Templates", "revenue": 28500, "orders": 342},
            {"category": "Licenses", "revenue": 12400, "orders": 156},
            {"category": "Plans", "revenue": 8900, "orders": 89},
            {"category": "Modules", "revenue": 6200, "orders": 45},
        ]
        top_pages = [
            {"path": "/dashboard", "views": 48230, "pct": 17.0},
            {"path": "/pricing", "views": 32140, "pct": 11.3},
            {"path": "/features", "views": 24890, "pct": 8.8},
            {"path": "/blog/template-trends-2026", "views": 18420, "pct": 6.5},
            {"path": "/docs/getting-started", "views": 15630, "pct": 5.5},
        ]
        top_countries = [
            {"country": "United States", "code": "US", "visitors": 12847, "pct": 30},
            {"country": "United Kingdom", "code": "GB", "visitors": 6423, "pct": 15},
            {"country": "Germany", "code": "DE", "visitors": 5134, "pct": 12},
            {"country": "Canada", "code": "CA", "visitors": 3847, "pct": 9},
            {"country": "France", "code": "FR", "visitors": 2983, "pct": 7},
            {"country": "Australia", "code": "AU", "visitors": 2418, "pct": 6},
        ]
        return render(request, "dashboard/analytics.html", {
            "stats": stats,
            "page_views_data": page_views,
            "category_data": category_revenue,
            "top_pages": top_pages,
            "top_countries": top_countries,
            "breadcrumbs": [("Dashboards", "/"), ("Analytics", None)],
        })


class CrmDashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        import json as _json
        from datetime import date
        from django.db.models import Count
        from django.utils import timezone
        from apps.tracking.models import Lead, all_brokers, broker_by_kind

        # Modello economico: lead non-FTD = costo €7; lead FTD = costo €300
        # (deposito) e premio €850. Profitto = guadagno − spesa.
        LEAD_COST, FTD_COST, FTD_PRIZE = 7, 300, 850   # FTD_PRIZE = default IT
        FOREIGN_LEAD_COST = 10                          # lead non-FTD ES/SE/DE
        FOREIGN_GEOS = ("ES", "SE", "DE")
        FTD_PRIZE_GEO = {"ES": 900, "DE": 1000, "SE": 1000}  # payout FTD per geo
        FTD_PRIZE_FACEBOOK = 725                        # payout FTD Link Facebook
        PENDING_COST = 250                             # lead depositato NON confermato (giallo)

        def eur(v):
            return "€" + f"{int(v):,}".replace(",", ".")

        # Filtro broker: ?broker=<kind>:<pk>. Vuoto = tutti.
        brokers_all = all_brokers()
        sel_val = request.GET.get("broker") or ""
        selected = None
        if ":" in sel_val:
            k, _, pid = sel_val.partition(":")
            selected = broker_by_kind(k, pid)
        # Filtro periodo: ?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD. Vuoto = tutto lo storico.
        from datetime import datetime as _dt
        from django.db.models import Q as _Q

        def _parse_date(raw):
            try:
                return _dt.strptime(raw, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                return None

        date_from_raw = request.GET.get("date_from") or ""
        date_to_raw = request.GET.get("date_to") or ""
        date_from = _parse_date(date_from_raw)
        date_to = _parse_date(date_to_raw)
        date_q = _Q()
        if date_from:
            date_q &= _Q(created_at__date__gte=date_from)
        if date_to:
            date_q &= _Q(created_at__date__lte=date_to)
        # Filtro paese: ?geo=IT|ES|DE|SE. Vuoto = tutti. Sul campo Lead.country
        # (non sul broker) cosi' resta corretto anche se un broker servisse piu' geo.
        GEO_OPTIONS = [("IT", "Italia"), ("ES", "Spagna"),
                       ("DE", "Germania"), ("SE", "Svezia")]
        geo_val = (request.GET.get("geo") or "").upper()
        geo_q = _Q(country=geo_val) if geo_val in dict(GEO_OPTIONS) else _Q()
        # Escludiamo i duplicati (is_duplicate) da TUTTI i conteggi/statistiche
        # e dalla ciambella. Restano visibili solo nella pagina Lead.
        leads = (Lead.for_broker(selected) if selected
                 else Lead.objects.all()).filter(is_duplicate=False)
        # Escludi i lead di TEST da spesa/guadagno/statistiche: "test" nel
        # nome, cognome o email, oppure status "Test" assegnato dal broker.
        # Restano visibili solo nella pagina Lead.
        _test_q = (_Q(firstname__icontains="test") | _Q(lastname__icontains="test")
                   | _Q(email__icontains="test") | _Q(status__iexact="test"))
        leads = (leads.filter(payload__has_key="login_url").exclude(_test_q)
                 .filter(date_q).filter(geo_q))
        brokers = [selected] if selected else brokers_all
        broker_options = [{"value": f"{b.kind}:{b.pk}", "name": b.name}
                          for b in sorted(brokers_all, key=lambda b: b.name.lower())]

        total = leads.count()
        ftd = leads.filter(is_deposit=True).count()
        non_ftd = total - ftd
        # Prezzi variabili per broker (Link Facebook) e per geo (ES/SE/DE).
        from django.contrib.contenttypes.models import ContentType as _CT
        from django.db.models import Q as _Qb
        _fb_q = _Qb(pk__in=[])
        _fb_keys = set()
        for _b in brokers_all:
            if "facebook" in _b.name.lower():
                _ct = _CT.objects.get_for_model(type(_b))
                _fb_q |= _Qb(broker_content_type=_ct, broker_object_id=_b.pk)
                _fb_keys.add((_ct.id, _b.pk))

        def lead_cost(qs):
            nf = qs.filter(is_deposit=False)
            nf_tot = nf.count()
            giallo = nf.filter(payload__deposit_pending=True).count()
            estero_tot = nf.filter(country__in=FOREIGN_GEOS).count()
            estero_giallo = nf.filter(payload__deposit_pending=True,
                                      country__in=FOREIGN_GEOS).count()
            estero = estero_tot - estero_giallo        # esteri NON gialli
            interno = (nf_tot - giallo) - estero       # italiani NON gialli
            return giallo * PENDING_COST + estero * FOREIGN_LEAD_COST + interno * LEAD_COST

        def ftd_revenue(qs):
            fq = qs.filter(is_deposit=True)
            fb = fq.filter(_fb_q).count()
            rest = fq.exclude(_fb_q)
            es = rest.filter(country="ES").count()
            de = rest.filter(country="DE").count()
            se = rest.filter(country="SE").count()
            other = rest.count() - es - de - se
            return (fb * FTD_PRIZE_FACEBOOK + es * FTD_PRIZE_GEO["ES"]
                    + de * FTD_PRIZE_GEO["DE"] + se * FTD_PRIZE_GEO["SE"]
                    + other * FTD_PRIZE)

        def lead_value(l):
            if l.is_deposit:
                if (l.broker_content_type_id, l.broker_object_id) in _fb_keys:
                    return FTD_PRIZE_FACEBOOK
                return FTD_PRIZE_GEO.get((l.country or "").upper(), FTD_PRIZE)
            if (l.payload or {}).get("deposit_pending"):
                return PENDING_COST
            return FOREIGN_LEAD_COST if (l.country or "").upper() in FOREIGN_GEOS else LEAD_COST
        # Guadagno TOTALE da tutte le FTD; le FTD gia' pagate (ftd_paid) sono
        # gia' state incassate → il KPI "Guadagno" mostra solo il DA INCASSARE.
        # Il Profitto resta calcolato sul TOTALE (non si falsa).
        guadagno_totale = ftd_revenue(leads)
        incassato = ftd_revenue(leads.filter(ftd_paid=True))
        guadagno = guadagno_totale - incassato   # ancora da incassare
        spesa = lead_cost(leads) + ftd * FTD_COST
        profitto = guadagno_totale - spesa
        win_rate = round(ftd * 100 / total, 1) if total else 0
        n_brokers = sum(1 for b in brokers if b.is_active)

        # Serie per-mese (ultimi 12 mesi).
        today = timezone.localdate()
        seq = []
        for i in range(11, -1, -1):
            m2, y2 = today.month - i, today.year
            while m2 <= 0:
                m2 += 12
                y2 -= 1
            seq.append((y2, m2))
        labels, lead_m, ftd_m, guad_m, prof_m = [], [], [], [], []
        for (y2, m2) in seq:
            qs = leads.filter(created_at__year=y2, created_at__month=m2)
            lc = qs.count()
            fc = qs.filter(is_deposit=True).count()
            labels.append(date(y2, m2, 1).strftime("%b"))
            lead_m.append(lc)
            ftd_m.append(fc)
            g = ftd_revenue(qs)
            s = lead_cost(qs) + fc * FTD_COST
            guad_m.append(g)
            prof_m.append(g - s)

        stats = [
            {"label": "Broker", "value": str(n_brokers), "delta": "", "trend": "up",
             "icon": "building-2", "accent": "#16a34a", "spark": _json.dumps(lead_m)},
            {"label": "Guadagno (da incassare)", "value": eur(guadagno), "delta": "", "trend": "up",
             "icon": "trophy", "accent": "#0891b2", "spark": _json.dumps(guad_m)},
            {"label": "Tasso FTD", "value": f"{win_rate}%", "delta": "", "trend": "up",
             "icon": "target", "accent": "#6366f1", "spark": _json.dumps(ftd_m)},
            {"label": "Profitto", "value": eur(profitto), "delta": "", "trend": "up" if profitto >= 0 else "down",
             "icon": "dollar-sign", "accent": "#d97706", "spark": _json.dumps(prof_m)},
        ]
        pipeline = {"categories": labels, "value": guad_m, "count": ftd_m}

        # Ciambella: lead per stato canonico. FTD = fonte di verità `is_deposit`;
        # gli altri stati vengono dal testo grezzo del broker, accorpato in bucket.
        counts = {}
        ftd_n = leads.filter(is_deposit=True).count()
        if ftd_n:
            counts["ftd"] = ftd_n
        for r in leads.filter(is_deposit=False).values("status").annotate(n=Count("id")):
            b = status_bucket(r["status"])
            if b == "ftd":  # status dice ftd ma non è depositante → è comunque lavorato
                b = "other"
            counts[b] = counts.get(b, 0) + r["n"]
        deal_stages = [
            {"name": label, "value": counts[key], "color": color}
            for key, label, color in STATUS_BUCKETS if counts.get(key)
        ] or [{"name": "nessun lead", "value": 0, "color": "#94a3b8"}]

        # Tabella: performance per broker.
        sales_reps = []
        for b in sorted(brokers, key=lambda x: x.name.lower()):
            bl = (Lead.for_broker(b).filter(is_duplicate=False)
                  .filter(payload__has_key="login_url").exclude(_test_q)
                  .filter(date_q).filter(geo_q))
            bt = bl.count()
            bf = bl.filter(is_deposit=True).count()
            sales_reps.append({
                "name": b.name, "initials": (b.name[:2]).upper(), "role": b.kind_label,
                "won": bf, "revenue": ftd_revenue(bl),
                "rate": round(bf * 100 / bt) if bt else 0,
            })

        # Bar chart: lead per broker.
        lead_sources = [{"source": b.name,
                         "leads": Lead.for_broker(b).filter(is_duplicate=False)
                                      .filter(payload__has_key="login_url")
                                      .exclude(_test_q).filter(date_q).filter(geo_q).count()}
                        for b in sorted(brokers, key=lambda x: x.name.lower())]

        # Tabella: lead recenti.
        recent_deals = []
        for l in leads.order_by("-created_at")[:6]:
            recent_deals.append({
                "deal": l.full_name or l.email or l.click_id,
                "company": l.broker_name or "—",
                "value": lead_value(l),
                "stage": "won" if l.is_deposit else "qualified",
                "close": l.created_at.strftime("%d/%m"),
            })

        targets = [
            {"label": "Guadagno", "current": guadagno_totale, "target": max(guadagno_totale * 2, 1000),
             "accent": "#16a34a", "is_money": False, "suffix": " €"},
            {"label": "Spesa", "current": spesa, "target": max(spesa * 2, 1000),
             "accent": "#d97706", "is_money": False, "suffix": " €"},
            {"label": "FTD", "current": ftd, "target": max(ftd * 2, 10),
             "accent": "#0891b2", "is_money": False},
        ]
        # Report settimanale (settimane lun→dom, ultime 8).
        from datetime import timedelta
        monday = today - timedelta(days=today.weekday())
        weeks = []
        for i in range(0, 8):
            ws = monday - timedelta(weeks=i)
            we = ws + timedelta(days=6)
            wqs = leads.filter(created_at__date__gte=ws, created_at__date__lte=we)
            wl = wqs.count()
            wf = wqs.filter(is_deposit=True).count()
            wnf = wl - wf
            wg = ftd_revenue(wqs)
            wsp = lead_cost(wqs) + wf * FTD_COST
            weeks.append({
                "label": f"{ws.strftime('%d/%m')}–{we.strftime('%d/%m')}",
                "in_corso": (i == 0),
                "leads": wnf, "ftd": wf,
                "spesa": eur(wsp), "guadagno": eur(wg), "profitto": eur(wg - wsp),
            })

        return render(request, "dashboard/crm.html", {
            "stats": stats,
            "pipeline_data": pipeline,
            "deal_stages_data": deal_stages,
            "lead_sources_data": lead_sources,
            "sales_reps": sales_reps,
            "recent_deals": recent_deals,
            "targets": targets,
            "weeks": weeks,
            "broker_options": broker_options,
            "selected_broker": sel_val,
            "selected_broker_name": selected.name if selected else "",
            "selected_date_from": date_from_raw if date_from else "",
            "selected_date_to": date_to_raw if date_to else "",
            "geo_options": [{"value": k, "name": v} for k, v in GEO_OPTIONS],
            "selected_geo": geo_val if geo_val in dict(GEO_OPTIONS) else "",
            "econ": {"lead": total, "ftd": ftd, "non_ftd": non_ftd,
                     "guadagno": eur(guadagno), "incassato": eur(incassato),
                     "totale": eur(guadagno_totale),
                     "ftd_pagate": leads.filter(ftd_paid=True).count(),
                     "spesa": eur(spesa), "profitto": eur(profitto)},
            "breadcrumbs": [("Dashboards", "/"), ("CRM", None)],
        })


class EcommerceDashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        stats = [
            _stat("Total Sales", "$128,430", "+18.2%", "up", "dollar-sign", "#16a34a",
                  [42, 48, 45, 53, 60, 58, 65, 70, 68, 75, 80, 85]),
            _stat("Avg Order Value", "$64.50", "+4.8%", "up", "shopping-bag", "#0891b2",
                  [55, 52, 58, 56, 60, 59, 62, 58, 63, 61, 64, 65]),
            _stat("Conversion Rate", "3.24%", "+0.8%", "up", "trending-up", "#6366f1",
                  [28, 30, 29, 31, 30, 32, 31, 33, 32, 34, 33, 32]),
            _stat("Refund Rate", "2.1%", "-0.3%", "up", "rotate-ccw", "#d97706",
                  [25, 23, 24, 22, 23, 21, 22, 20, 21, 20, 21, 21]),
        ]
        # 30 days of sales — simple sin wave for demo curve
        import math as _m
        daily = []
        for i in range(30):
            base = 3200 + _m.sin(i * 0.3) * 800
            revenue = round(base + (600 if i > 20 else 0))
            orders = round(revenue / 62 + _m.sin(i * 0.5) * 8)
            profit = round(revenue * (0.28 + _m.sin(i * 0.4) * 0.06))
            daily.append({"date": f"Feb {i + 1}", "revenue": revenue,
                          "orders": orders, "profit": profit})
        order_status = [
            {"name": "Completed", "value": 584},
            {"name": "Processing", "value": 234},
            {"name": "Pending", "value": 127},
            {"name": "Cancelled", "value": 47},
        ]
        top_products = [
            {"name": "Pro Dashboard Template", "price": 49.99, "sold": 342, "revenue": 17096.58},
            {"name": "Enterprise License",     "price": 199.99,"sold": 124, "revenue": 24798.76},
            {"name": "UI Component Kit",       "price": 29.99, "sold": 287, "revenue": 8607.13},
            {"name": "Admin Starter Pack",     "price": 39.99, "sold": 198, "revenue": 7918.02},
            {"name": "Analytics Module",       "price": 39.99, "sold": 156, "revenue": 6238.44},
            {"name": "Email Template Pack",    "price": 14.99, "sold": 412, "revenue": 6175.88},
        ]
        sales_by_category = [
            {"category": "Templates", "revenue": 48420},
            {"category": "Licenses", "revenue": 32180},
            {"category": "Plans", "revenue": 24600},
            {"category": "Modules", "revenue": 16240},
            {"category": "Add-ons", "revenue": 6990},
        ]
        recent_transactions = [
            {"customer": "Sarah Chen",     "initials": "SC", "product": "Pro Dashboard Template",
             "amount": 49.99,  "status": "completed",  "date": "Feb 22"},
            {"customer": "Marcus Johnson", "initials": "MJ", "product": "Enterprise License",
             "amount": 199.99, "status": "completed",  "date": "Feb 22"},
            {"customer": "Priya Sharma",   "initials": "PS", "product": "UI Component Kit",
             "amount": 29.99,  "status": "processing", "date": "Feb 21"},
            {"customer": "Alex Rivera",    "initials": "AR", "product": "Admin Starter Pack",
             "amount": 39.99,  "status": "completed",  "date": "Feb 21"},
            {"customer": "Emma Taylor",    "initials": "ET", "product": "Analytics Module",
             "amount": 39.99,  "status": "pending",    "date": "Feb 20"},
            {"customer": "David Park",     "initials": "DP", "product": "Email Template Pack",
             "amount": 14.99,  "status": "cancelled",  "date": "Feb 20"},
        ]
        targets = [
            {"label": "Monthly Revenue", "current": 128430, "target": 150000,
             "accent": "#16a34a", "is_money": True},
            {"label": "Orders",          "current": 992,    "target": 1200,
             "accent": "#0891b2", "is_money": False},
            {"label": "New Customers",   "current": 347,    "target": 500,
             "accent": "#6366f1", "is_money": False},
        ]
        return render(request, "dashboard/ecommerce.html", {
            "stats": stats,
            "daily_sales_data": daily,
            "order_status_data": order_status,
            "category_data": sales_by_category,
            "top_products": top_products,
            "recent_transactions": recent_transactions,
            "targets": targets,
            "breadcrumbs": [("Dashboards", "/"), ("eCommerce", None)],
        })


class SaasDashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        stats = [
            _stat("MRR", "$48.2K", "+8.4%", "up", "dollar-sign", "#16a34a",
                  [32, 35, 33, 37, 38, 40, 39, 42, 44, 45, 47, 48]),
            _stat("Active Users", "2,847", "+12.6%", "up", "users", "#0891b2",
                  [18, 20, 19, 22, 23, 21, 24, 25, 24, 26, 27, 28]),
            _stat("Churn Rate", "3.2%", "-0.5%", "up", "user-minus", "#6366f1",
                  [42, 40, 41, 38, 37, 39, 36, 35, 34, 34, 33, 32]),
            _stat("Trial Conversion", "24.8%", "+2.3%", "up", "user-check", "#d97706",
                  [18, 19, 18, 20, 21, 20, 22, 23, 22, 24, 24, 25]),
        ]
        revenue_growth = {
            "categories": ["Mar", "Apr", "May", "Jun", "Jul", "Aug",
                           "Sep", "Oct", "Nov", "Dec", "Jan", "Feb"],
            "mrr":  [31200, 32800, 33500, 35100, 36400, 37800,
                     39200, 40600, 42500, 44100, 46300, 48200],
            "arr":  [374400, 393600, 402000, 421200, 436800, 453600,
                     470400, 487200, 510000, 529200, 555600, 578400],
        }
        plans = [
            {"name": "Free",       "value": 842},
            {"name": "Starter",    "value": 1234},
            {"name": "Pro",        "value": 628},
            {"name": "Enterprise", "value": 143},
        ]
        marketing_channels = [
            {"channel": "Organic Search", "visitors": 18420, "signups": 842, "conv": 4.6, "cpa": 0},
            {"channel": "Paid Ads",       "visitors": 9240,  "signups": 416, "conv": 4.5, "cpa": 38},
            {"channel": "Social Media",   "visitors": 6830,  "signups": 241, "conv": 3.5, "cpa": 24},
            {"channel": "Email",          "visitors": 4120,  "signups": 318, "conv": 7.7, "cpa": 12},
            {"channel": "Referrals",      "visitors": 3290,  "signups": 198, "conv": 6.0, "cpa": 18},
            {"channel": "Direct",         "visitors": 5640,  "signups": 167, "conv": 3.0, "cpa": 0},
        ]
        user_growth = {
            "categories": ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb"],
            "new": [284, 312, 298, 341, 378, 356],
        }
        recent_signups = [
            {"name": "Sofia Andersen", "initials": "SA",
             "email": "sofia@nordloop.io",   "plan": "pro",        "date": "Feb 22"},
            {"name": "Marcus Webb",    "initials": "MW",
             "email": "m.webb@stackfire.com","plan": "starter",    "date": "Feb 22"},
            {"name": "Priya Kulkarni", "initials": "PK",
             "email": "priya@brightpath.app","plan": "enterprise", "date": "Feb 21"},
            {"name": "Tomas Barrera",  "initials": "TB",
             "email": "tomas@veloz.mx",      "plan": "pro",        "date": "Feb 21"},
            {"name": "Yuki Tanaka",    "initials": "YT",
             "email": "yuki@launchpad.jp",   "plan": "free",       "date": "Feb 20"},
            {"name": "Amara Osei",     "initials": "AO",
             "email": "amara@growcraft.ng",  "plan": "starter",    "date": "Feb 20"},
        ]
        targets = [
            {"label": "MRR Target",         "current": 48200, "target": 60000,
             "accent": "#16a34a", "is_money": True,  "suffix": ""},
            {"label": "Active Users",       "current": 2847,  "target": 3500,
             "accent": "#0891b2", "is_money": False, "suffix": ""},
            {"label": "Trial → Paid Conv.", "current": 24.8,  "target": 30,
             "accent": "#d97706", "is_money": False, "suffix": "%"},
        ]
        return render(request, "dashboard/saas.html", {
            "stats": stats,
            "revenue_growth_data": revenue_growth,
            "plans_data": plans,
            "user_growth_data": user_growth,
            "marketing_channels": marketing_channels,
            "recent_signups": recent_signups,
            "targets": targets,
            "breadcrumbs": [("Dashboards", "/"), ("SaaS", None)],
        })


@login_required
def revenue_chart_data(request):
    range_key = request.GET.get("range", "7d")
    data = {
        "7d": {
            "categories": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "series": [
                {"name": "Revenue", "data": [4400, 5500, 5700, 5600, 6100, 5800, 6400]},
                {"name": "Orders",  "data": [  42,   58,   55,   61,   67,   63,   74]},
            ],
        },
        "30d": {
            "categories": [f"D{i}" for i in range(1, 31)],
            "series": [
                {"name": "Revenue", "data": [4000 + i * 100 for i in range(30)]},
                {"name": "Orders",  "data": [  40 + i *   2 for i in range(30)]},
            ],
        },
        "90d": {
            "categories": [f"W{i}" for i in range(1, 13)],
            "series": [
                {"name": "Revenue", "data": [40000 + i * 1200 for i in range(12)]},
                {"name": "Orders",  "data": [  420 + i *   15 for i in range(12)]},
            ],
        },
    }
    return JsonResponse(data.get(range_key, data["7d"]))
