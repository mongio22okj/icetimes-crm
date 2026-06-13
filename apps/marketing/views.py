"""Marketing landing variants + pricing + support. All public — no auth.

Each variant view sets its own `features` + `testimonials` context.
Hardcoded copy lives here, not in DB. Support form persists submissions
in SupportTicket.
"""
import secrets
import time

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from apps.marketing.forms import SupportForm

_TESTIMONIALS = [
    {
        "quote": "Apex cut our reporting overhead in half. We finally see the same numbers across teams.",
        "name": "Sara Chen", "role": "VP Operations, North Loop",
    },
    {
        "quote": "The dashboard ships with everything we'd otherwise spend a quarter building from scratch.",
        "name": "Marcus Patel", "role": "CTO, Vellum Logistics",
    },
    {
        "quote": "Setup took an afternoon. We invoice and track from one place now.",
        "name": "Laila Okafor", "role": "Founder, Olive & Mint",
    },
]


_HUB_PLATFORM_FEATURES = [
    {"icon": "users",          "title": "Auth + 2FA",
     "body": "Login, signup, password reset, email verification, sudo-mode confirm, TOTP recovery codes."},
    {"icon": "bell",           "title": "Live notifications",
     "body": "HTMX-polled bell, mark-read, per-event dispatch helpers — wired into invoices, orders, mail."},
    {"icon": "layout-dashboard", "title": "8 ApexCharts variants",
     "body": "Bar, line, area, donut, radial, heatmap, scatter, mixed — themed light & dark out of the box."},
    {"icon": "settings",       "title": "Tabbed settings",
     "body": "Profile / Password / Appearance / Two-factor — and a sudo-mode mixin for sensitive actions."},
    {"icon": "file-text",      "title": "PDF export",
     "body": "WeasyPrint-backed invoice PDFs with public token URLs your customers can pay from."},
    {"icon": "package",        "title": "Internationalized",
     "body": "Django i18n wired end-to-end with a Spanish demo locale and a header language picker."},
]

_HUB_HIGHLIGHTS = [
    {
        "eyebrow": "Workflow",
        "title": "Track the full revenue cycle",
        "body": "Customers, products, orders, and invoices share a relational schema. Generate an invoice from an order in one click — line items copy across, status transitions emit notifications, and clients pay via a public token URL.",
        "bullets": ["Soft-delete archives", "PDF + public sharing", "Status state machine"],
        "url_name": "marketing:ecommerce",
        "cta": "Explore eCommerce →",
    },
    {
        "eyebrow": "Communication",
        "title": "Mail and chat without infra",
        "body": "Three-pane mail with five folders, threading, star/trash. 1:1 chat with HTMX-polled message stream every 3 seconds. Both wire into the same Notification table.",
        "bullets": ["No SMTP / WebSockets", "Reply chains", "Bell badge auto-syncs"],
        "url_name": "marketing:saas",
        "cta": "See SaaS variant →",
    },
    {
        "eyebrow": "Productivity",
        "title": "Calendar, kanban, files",
        "body": "FullCalendar v6 with month/week/day, color categories, JSON event source. SortableJS-driven kanban with drag-between-columns. Per-user file browser with folder hierarchy and 10MB uploads.",
        "bullets": ["FullCalendar + SortableJS", "Drag-and-drop", "Hierarchical folders"],
        "url_name": "marketing:crm",
        "cta": "See CRM variant →",
    },
]

_HUB_FAQ = [
    {"q": "Do I need to know Django to use Apex?",
     "a": "Helpful, but not required. The codebase reads like a standard Django 5 project — class-based views, forms, templates. There's a CLAUDE.md walkthrough and 400+ tests as documentation."},
    {"q": "How long does setup take?",
     "a": "Under a minute on a fresh checkout: uv sync, npm run build, manage.py migrate, manage.py seed_demo. Detailed steps live in the README's Quick start section."},
    {"q": "Can I deploy this to production today?",
     "a": "Yes — env-driven settings, WhiteNoise for statics, gunicorn-ready WSGI. Switch DATABASE_URL to Postgres, set ALLOWED_HOSTS, collectstatic, and ship."},
    {"q": "Is there a paid version?",
     "a": "The codebase is shipped as-is under the DashboardPack license — no paid tier. The pricing page is a parity demo of how teams typically present plans."},
]


class LandingsHubView(TemplateView):
    template_name = "marketing/hub.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["platform_features"] = _HUB_PLATFORM_FEATURES
        ctx["highlights"] = _HUB_HIGHLIGHTS
        ctx["testimonials_list"] = _TESTIMONIALS
        ctx["faq"] = _HUB_FAQ
        return ctx


class AnalyticsView(TemplateView):
    template_name = "marketing/analytics.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["features_list"] = [
            {"icon": "activity", "title": "Real-time KPIs",
             "body": "Live event ingestion plus rollups so dashboards reflect the latest second."},
            {"icon": "layout-dashboard", "title": "Pre-built dashboards",
             "body": "Revenue, traffic, conversion and retention boards out of the box."},
            {"icon": "arrow-up-right", "title": "Drill-downs",
             "body": "From the executive summary to a single user session in two clicks."},
        ]
        ctx["testimonials_list"] = _TESTIMONIALS
        return ctx


class SaasView(TemplateView):
    template_name = "marketing/saas.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["features_list"] = [
            {"icon": "users", "title": "Multi-tenant ready",
             "body": "Workspace isolation, role-based access, audit trails."},
            {"icon": "dollar-sign", "title": "Built-in billing",
             "body": "Plans, seat-based pricing, invoicing — all native, no add-ons."},
            {"icon": "bell", "title": "Observability hooks",
             "body": "Notifications fire on every state change; export to your stack."},
        ]
        ctx["testimonials_list"] = _TESTIMONIALS
        return ctx


class CrmView(TemplateView):
    template_name = "marketing/crm.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["features_list"] = [
            {"icon": "user-plus", "title": "Contacts that scale",
             "body": "Soft-delete archives keep history; staff sees only what's active."},
            {"icon": "trello", "title": "Visual pipelines",
             "body": "Drag deals through stages on a Kanban board. Same UI as your tasks."},
            {"icon": "mail", "title": "Conversation history",
             "body": "Mail and chat tied to contacts so nothing falls through the cracks."},
        ]
        ctx["testimonials_list"] = _TESTIMONIALS
        return ctx


class EcommerceView(TemplateView):
    template_name = "marketing/ecommerce.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["features_list"] = [
            {"icon": "package", "title": "Catalog + inventory",
             "body": "Products with categories, stock, and protected references from orders."},
            {"icon": "shopping-cart", "title": "Order lifecycle",
             "body": "Pending → paid → shipped, with invoice generation in one click."},
            {"icon": "file-text", "title": "Invoices in seconds",
             "body": "PDF export with public token URLs your customers can pay from."},
        ]
        ctx["testimonials_list"] = _TESTIMONIALS
        return ctx


_PRICING_TIERS = [
    {
        "name": "Starter",
        "price_monthly": 0,
        "price_annual": 0,
        "blurb": "Try the dashboard with no commitment.",
        "features": [
            "1 user",
            "100 records per app",
            "Community support",
            "Email-only auth",
            "Light & dark themes",
            "1 GB file storage",
        ],
        "cta": "Start free",
        "highlight": False,
    },
    {
        "name": "Pro",
        "price_monthly": 29,
        "price_annual": 23,  # 20% off displayed
        "blurb": "Everything a small team needs.",
        "features": [
            "10 users",
            "Unlimited records",
            "Priority email support",
            "2FA + audit log",
            "10 GB file storage",
            "PDF export",
        ],
        "cta": "Upgrade to Pro",
        "highlight": True,
    },
    {
        "name": "Enterprise",
        "price_monthly": 99,
        "price_annual": 79,
        "blurb": "Custom-fit deployments.",
        "features": [
            "Unlimited users",
            "Custom domain",
            "Dedicated support",
            "SSO / SAML",
            "100 GB file storage",
            "On-prem option",
        ],
        "cta": "Contact sales",
        "highlight": False,
    },
]

_FAQ = [
    {
        "q": "Can I change plans later?",
        "a": "Yes — upgrades and downgrades take effect at the start of the next billing period.",
    },
    {
        "q": "Is there a setup fee?",
        "a": "No. Pricing is straightforward; you pay only for the plan you choose.",
    },
    {
        "q": "Do you offer non-profit pricing?",
        "a": "Yes — registered non-profits get 50% off the Pro plan. Contact us for details.",
    },
    {
        "q": "What's included in support?",
        "a": "Starter includes community Q&A. Pro adds priority email (within 1 business day). Enterprise gets a named support engineer.",
    },
    {
        "q": "Can I self-host?",
        "a": "The Enterprise plan includes a self-hosted option with our deployment guide and a 12-month license.",
    },
]


class PricingView(TemplateView):
    template_name = "marketing/pricing.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tiers"] = _PRICING_TIERS
        ctx["faq"] = _FAQ
        return ctx


_HELP_ARTICLES = [
    {"title": "Getting started", "summary": "Set up your first account, invite teammates, and explore the dashboard."},
    {"title": "Managing customers", "summary": "Best practices for organizing customer records, archiving, and filtering."},
    {"title": "Invoice workflows", "summary": "Draft → sent → paid lifecycle, plus how to share invoices with public links."},
    {"title": "Two-factor authentication", "summary": "Enable 2FA, generate recovery codes, and re-authenticate sensitive actions."},
    {"title": "Notifications & bell", "summary": "Configure what triggers a notification and how to mark them read."},
    {"title": "Files & storage", "summary": "Upload limits, folder organization, and the 10 MB per-file ceiling."},
]


class SupportView(View):
    template_name = "marketing/support.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": SupportForm(),
            "articles": _HELP_ARTICLES,
        })

    def post(self, request):
        form = SupportForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form,
                "articles": _HELP_ARTICLES,
            })
        form.save()
        messages.success(request, "Thanks — we'll be in touch within 1 business day.")
        return redirect("marketing:support")


# ── Phase 18 — Marketing polish ───────────────────────────────────────


class ChangelogView(TemplateView):
    """Renders CHANGELOG.md with per-release anchors. Public, no auth."""
    template_name = "marketing/changelog.html"

    def get_context_data(self, **kwargs):
        from apps.marketing.changelog import parse_changelog
        ctx = super().get_context_data(**kwargs)
        ctx["releases"] = parse_changelog()
        return ctx


class RoadmapView(TemplateView):
    """Public Now / Next / Later board. Data is hand-curated here so
    we can edit it without a deploy via PR; admin model can come later."""
    template_name = "marketing/roadmap.html"

    NOW = [
        {"phase": "14", "title": "Realtime via Django Channels",
         "blurb": "Live chat presence, kanban broadcasts, real-time bell — Redis-backed WebSocket layer."},
        {"phase": "16", "title": "Organizations + RBAC",
         "blurb": "Multi-tenant primitives — workspaces, members, invitations, role × permission matrix."},
    ]
    NEXT = [
        {"phase": "19a", "title": "Hosted documentation site",
         "blurb": "MkDocs Material at docs.colorlib.com/apex with recipes, deploy guides, API ref."},
        {"phase": "19b", "title": "One-click deploy recipes",
         "blurb": "Render, Fly.io, Railway, DigitalOcean App Platform — config files + screenshots."},
        {"phase": "19c", "title": "PWA + offline shell",
         "blurb": "Manifest + service worker (extends Phase 13 push) + installability."},
    ]
    LATER = [
        {"phase": "20", "title": "Frontend bundling (esbuild)",
         "blurb": "Replace CDN scripts with bundled, hashed, cache-busted ES modules."},
        {"phase": "21", "title": "Search backend",
         "blurb": "Postgres FTS via django.contrib.postgres.search with per-app result grouping."},
        {"phase": "22", "title": "Image optimization pipeline",
         "blurb": "Auto AVIF/WebP via post-save signals on uploads."},
        {"phase": "23", "title": "Mobile native shells",
         "blurb": "Capacitor wrappers around the existing PWA."},
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["columns"] = [
            {"key": "now", "label": "Now",
             "sub": "In flight — actively being built.", "items": self.NOW},
            {"key": "next", "label": "Next",
             "sub": "Up next — scoped, queued, scheduled.", "items": self.NEXT},
            {"key": "later", "label": "Later",
             "sub": "On the roadmap; no committed date.", "items": self.LATER},
        ]
        return ctx


class CompareView(TemplateView):
    """Comparison table — Apex vs hand-rolled vs typical premium template."""
    template_name = "marketing/compare.html"

    ROWS = [
        ("category", "Foundation", None, None, None),
        ("row", "Real Django backend", True, "—", "Sometimes (often React-only)"),
        ("row", "Persists to a real database", True, "—", "Mock data only"),
        ("row", "20+ feature apps shipped end-to-end", True, "Build it", "≤10 typically"),
        ("row", "Auth + 2FA + email verification", True, "Days of work", "Sometimes"),
        ("row", "Tests included (900+ unit + 20+ E2E)", True, "—", "Rare"),
        ("category", "UI surfaces", None, None, None),
        ("row", "26 documented UI primitives", True, "Build them", "Variable"),
        ("row", "HTMX-driven datatable on every list view", True, "Days of work", "Sometimes"),
        ("row", "12 polished form widgets (floating labels, multi-select, dropzone, etc.)", True, "Days of work", "Sometimes"),
        ("row", "5 dashboard variants + 7 marketing landings", True, "—", "1–3 typically"),
        ("category", "Integrations", None, None, None),
        ("row", "REST API with OpenAPI/Swagger (Django Ninja)", True, "Days–weeks", "Rare"),
        ("row", "Signed outbound webhooks", True, "Days of work", "Rare"),
        ("row", "Notification center with categories + push scaffold", True, "Days of work", "Rare"),
        ("row", "PDF invoices via WeasyPrint", True, "Hours", "Rare"),
        ("category", "Operations", None, None, None),
        ("row", "Settings depth (sessions, audit log, data export, deletion)", True, "Days of work", "Rare"),
        ("row", "Per-user API tokens with one-time reveal", True, "Hours", "Rare"),
        ("row", "i18n shipped (English + Spanish)", True, "Hours", "Sometimes"),
        ("row", "Dockerfile + WhiteNoise (no nginx required)", True, "Hours", "Sometimes"),
    ]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rows"] = self.ROWS
        return ctx


class ShowcaseView(TemplateView):
    """One-page index of every demo surface in the kit."""
    template_name = "marketing/showcase.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sections"] = [
            {
                "title": "Dashboards",
                "blurb": "Five dashboards at /, /dashboards/{analytics,crm,ecommerce,saas}/.",
                "links": [
                    ("Overview", "/", "layout-dashboard"),
                    ("Analytics", "/dashboards/analytics/", "bar-chart-3"),
                    ("CRM", "/dashboards/crm/", "trending-up"),
                    ("eCommerce", "/dashboards/ecommerce/", "shopping-bag"),
                    ("SaaS", "/dashboards/saas/", "rocket"),
                ],
            },
            {
                "title": "Component library",
                "blurb": "26 reusable UI primitives — modal, drawer, toast, tabs, accordion, datepicker, dropzone…",
                "links": [
                    ("Index of all primitives", "/components/", "blocks"),
                    ("Modal", "/components/modal/", "square-stack"),
                    ("Tabs", "/components/tabs/", "layout"),
                    ("Toast", "/components/toast/", "bell"),
                    ("Date range picker", "/components/daterange/", "calendar-range"),
                    ("File dropzone", "/components/dropzone/", "upload-cloud"),
                ],
            },
            {
                "title": "Forms gallery",
                "blurb": "Real Django form widgets with floating labels, validation states, sizes.",
                "links": [
                    ("All form widgets", "/pages/forms/", "file-text"),
                ],
            },
            {
                "title": "Datatable",
                "blurb": "HTMX-driven sort + filter + bulk actions + saved views + CSV/XLSX/PDF export.",
                "links": [
                    ("Datatable showcase", "/pages/datatable/", "trello"),
                    ("Customers (live)", "/customers/", "user-plus"),
                    ("Invoices (live)", "/invoices/", "file-text"),
                ],
            },
            {
                "title": "Charts",
                "blurb": "8 ApexCharts variants, all theme-aware (light + dark).",
                "links": [
                    ("Charts showcase", "/charts/", "activity"),
                ],
            },
            {
                "title": "Productivity apps",
                "blurb": "Mail, chat, calendar, kanban, files, projects, profiles.",
                "links": [
                    ("Mail", "/mail/", "mail"),
                    ("Chat", "/chat/", "message-circle"),
                    ("Calendar", "/calendar/", "calendar"),
                    ("Kanban", "/kanban/", "trello"),
                    ("Files", "/files/", "folder"),
                    ("Projects", "/projects/", "briefcase"),
                ],
            },
            {
                "title": "API + integrations",
                "blurb": "REST API with Swagger UI, signed webhooks, browser-push scaffold.",
                "links": [
                    ("Swagger UI", "/api/v1/docs", "book-open"),
                    ("OpenAPI schema", "/api/v1/openapi.json", "file-text"),
                    ("Webhooks settings", "/settings/webhooks/", "rocket"),
                ],
            },
            {
                "title": "Pages & status",
                "blurb": "Coming-soon, maintenance, 503, error pages.",
                "links": [
                    ("Coming soon", "/pages/coming-soon/", "rocket"),
                    ("Maintenance", "/pages/maintenance/", "settings"),
                    ("Maps showcase", "/pages/maps/", "map-pin"),
                    ("Widgets gallery", "/pages/widgets/", "package"),
                ],
            },
        ]
        return ctx


# ── Lead-capture landings (public, no auth) ─────────────────────────────

class LandingDetailView(TemplateView):
    """Public landing — renders a LandingPage row by slug.

    Query string can override the pre-set tracking values for A/B tests
    or per-ad-group customization, e.g.:
        /landing/trading/?funnel=trading-2026-B&source=GoogleAds&sub=kw-99
    """
    template_name = "marketing/landing_public.html"

    def get_context_data(self, **kwargs):
        from django.http import Http404

        from apps.marketing.models import LandingPage

        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get("slug")
        try:
            landing = LandingPage.objects.get(slug=slug, is_active=True)
        except LandingPage.DoesNotExist:
            raise Http404("Landing not found")
        q = self.request.GET
        ctx["landing"] = landing
        ctx["funnel"] = q.get("funnel") or landing.funnel
        ctx["source_tag"] = q.get("source") or landing.source_tag
        ctx["sub"] = q.get("sub") or landing.sub
        return ctx


@method_decorator(csrf_exempt, name="dispatch")
class LandingSubmitView(View):
    """Server-side intake for the public landing pages.

    Builds a Lead row directly (without going through the public postback
    endpoint) so the page can show an inline success message and the
    postback token is never exposed in the browser. The submitting page
    sends `variant` (= landing slug) so we tag the lead's source field.
    """

    def post(self, request):
        from apps.leads.models import Lead

        data = request.POST
        email = (data.get("email") or "").strip()
        if not email:
            return JsonResponse({"ok": False, "error": "email required"}, status=400)

        variant = (data.get("variant") or "landing").strip()[:32]
        uniqueid = f"land-{variant}-{int(time.time())}-{secrets.token_hex(3)}"
        payload = {k: v for k, v in data.items() if k != "csrfmiddlewaretoken"}

        lead = Lead.objects.create(
            uniqueid=uniqueid,
            firstname=(data.get("firstname") or "").strip()[:120],
            lastname=(data.get("lastname") or "").strip()[:120],
            email=email[:254],
            phone=(data.get("phone") or "").strip()[:32],
            country=(data.get("country") or "").strip().upper()[:8],
            status=(data.get("status") or "lead").strip()[:120],
            source=f"landing-{variant}"[:64],
            payload=payload,
        )
        return JsonResponse({"ok": True, "id": lead.pk})


# ── Landing admin CRUD (staff-only) ─────────────────────────────────────

from django.contrib.auth.mixins import LoginRequiredMixin  # noqa: E402
from django.urls import reverse_lazy  # noqa: E402
from django.views.generic import CreateView, DeleteView, ListView, UpdateView  # noqa: E402

from apps.accounts.mixins import EmailVerifiedRequiredMixin  # noqa: E402
from apps.accounts.views import StaffRequiredMixin  # noqa: E402
from apps.core.breadcrumbs import BreadcrumbsMixin  # noqa: E402
from apps.core.messages import LEVEL_SUCCESS, toast  # noqa: E402


class LandingPageListView(BreadcrumbsMixin, LoginRequiredMixin,
                          EmailVerifiedRequiredMixin, StaffRequiredMixin,
                          ListView):
    template_name = "marketing/landing_admin_list.html"
    context_object_name = "landings"
    breadcrumb_title = "Landing Pages"

    def get_queryset(self):
        from apps.marketing.models import LandingPage
        return LandingPage.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.products.models import Product
        ctx["product_landings"] = Product.objects.exclude(status="archived").order_by("-created_at")
        return ctx


class LandingPageCreateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            CreateView):
    template_name = "marketing/landing_admin_form.html"
    success_url = reverse_lazy("marketing:landing_admin_list")
    breadcrumb_title = "Nuova landing"
    breadcrumb_parent = ("Landing Pages", "marketing:landing_admin_list")

    def get_form_class(self):
        from apps.marketing.forms import LandingPageForm
        return LandingPageForm

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Landing '{self.object.title}' creata.")
        return response


class LandingPageUpdateView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, StaffRequiredMixin,
                            UpdateView):
    template_name = "marketing/landing_admin_form.html"
    success_url = reverse_lazy("marketing:landing_admin_list")
    breadcrumb_title = "Modifica landing"
    breadcrumb_parent = ("Landing Pages", "marketing:landing_admin_list")

    def get_queryset(self):
        from apps.marketing.models import LandingPage
        return LandingPage.objects.all()

    def get_form_class(self):
        from apps.marketing.forms import LandingPageForm
        return LandingPageForm

    def form_valid(self, form):
        response = super().form_valid(form)
        toast(self.request, LEVEL_SUCCESS,
              f"Landing '{self.object.title}' aggiornata.")
        return response


class LandingPageDeleteView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                            StaffRequiredMixin, DeleteView):
    success_url = reverse_lazy("marketing:landing_admin_list")

    def get_queryset(self):
        from apps.marketing.models import LandingPage
        return LandingPage.objects.all()

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        title = obj.title
        obj.delete()
        toast(request, LEVEL_SUCCESS, f"Landing '{title}' eliminata.")
        return redirect(self.success_url)
