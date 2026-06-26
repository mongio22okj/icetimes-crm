import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.orders.models import Order

User = get_user_model()


class DashboardView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def get(self, request):
        from apps.tracking.models import Lead, all_brokers
        from django.utils import timezone

        leads = Lead.objects.all()
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
            bl = Lead.for_broker(b)
            by_broker.append({"name": b.name, "leads": bl.count(),
                              "ftd": bl.filter(is_deposit=True).count()})
        recent_leads = leads.order_by("-created_at")[:10]
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
        from apps.tracking.models import Lead, all_brokers

        # Modello economico: lead non-FTD = costo €7; lead FTD = costo €300
        # (deposito) e premio €850. Profitto = guadagno − spesa.
        LEAD_COST, FTD_COST, FTD_PRIZE = 7, 300, 850

        def eur(v):
            return "€" + f"{int(v):,}".replace(",", ".")

        leads = Lead.objects.all()
        total = leads.count()
        ftd = leads.filter(is_deposit=True).count()
        non_ftd = total - ftd
        guadagno = ftd * FTD_PRIZE
        spesa = non_ftd * LEAD_COST + ftd * FTD_COST
        profitto = guadagno - spesa
        win_rate = round(ftd * 100 / total, 1) if total else 0
        brokers = all_brokers()
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
            g = fc * FTD_PRIZE
            s = (lc - fc) * LEAD_COST + fc * FTD_COST
            guad_m.append(g)
            prof_m.append(g - s)

        stats = [
            {"label": "Broker", "value": str(n_brokers), "delta": "", "trend": "up",
             "icon": "building-2", "accent": "#16a34a", "spark": _json.dumps(lead_m)},
            {"label": "Guadagno", "value": eur(guadagno), "delta": "", "trend": "up",
             "icon": "trophy", "accent": "#0891b2", "spark": _json.dumps(guad_m)},
            {"label": "Tasso FTD", "value": f"{win_rate}%", "delta": "", "trend": "up",
             "icon": "target", "accent": "#6366f1", "spark": _json.dumps(ftd_m)},
            {"label": "Profitto", "value": eur(profitto), "delta": "", "trend": "up" if profitto >= 0 else "down",
             "icon": "dollar-sign", "accent": "#d97706", "spark": _json.dumps(prof_m)},
        ]
        pipeline = {"categories": labels, "value": guad_m, "count": ftd_m}

        # Ciambella: lead per stato.
        by_status = list(leads.values("status").annotate(n=Count("id")).order_by("-n"))
        deal_stages = [{"name": (r["status"] or "nuovo"), "value": r["n"]} for r in by_status] \
            or [{"name": "nessun lead", "value": 0}]

        # Tabella: performance per broker.
        sales_reps = []
        for b in sorted(brokers, key=lambda x: x.name.lower()):
            bl = Lead.for_broker(b)
            bt = bl.count()
            bf = bl.filter(is_deposit=True).count()
            sales_reps.append({
                "name": b.name, "initials": (b.name[:2]).upper(), "role": b.kind_label,
                "won": bf, "revenue": bf * FTD_PRIZE,
                "rate": round(bf * 100 / bt) if bt else 0,
            })

        # Bar chart: lead per broker.
        lead_sources = [{"source": b.name, "leads": Lead.for_broker(b).count()}
                        for b in sorted(brokers, key=lambda x: x.name.lower())]

        # Tabella: lead recenti.
        recent_deals = []
        for l in leads.order_by("-created_at")[:6]:
            recent_deals.append({
                "deal": l.full_name or l.email or l.click_id,
                "company": l.broker_name or "—",
                "value": FTD_PRIZE if l.is_deposit else LEAD_COST,
                "stage": "won" if l.is_deposit else "qualified",
                "close": l.created_at.strftime("%d/%m"),
            })

        targets = [
            {"label": "Guadagno", "current": guadagno, "target": max(guadagno * 2, 1000),
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
            wg = wf * FTD_PRIZE
            wsp = wnf * LEAD_COST + wf * FTD_COST
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
            "econ": {"lead": total, "ftd": ftd, "non_ftd": non_ftd,
                     "guadagno": eur(guadagno), "spesa": eur(spesa), "profitto": eur(profitto)},
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
