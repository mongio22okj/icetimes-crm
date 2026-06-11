from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def csrf_failure(request, reason=""):
    """Friendlier CSRF reject page than Django's bare-bones default.

    Wired via CSRF_FAILURE_VIEW in settings/base.py. The most common
    visible cause on the public demo is the hourly reseed cron flushing
    sessions while a form is open — telling the user to refresh fixes
    it 100% of the time.
    """
    return render(request, "errors/403_csrf.html",
                  {"reason": reason}, status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


# ── Status / launch pages ──────────────────────────────────────────────
# Static showcase pages buyers can drop into their site as starting
# points for pre-launch / scheduled-downtime / outage scenarios.

def coming_soon(request):
    """Public pre-launch page with countdown timer + email signup form."""
    # Default countdown target: 14 days out so the page demos a full
    # countdown without dropping to zero on first visit.
    launch_at = timezone.now() + timedelta(days=14, hours=6, minutes=42)
    return render(request, "pages/coming_soon.html", {
        "launch_at": launch_at,
        "subscribed": request.GET.get("subscribed") == "1",
    })


def coming_soon_subscribe(request):
    """Stub email-capture endpoint for the coming-soon form. Demo only —
    just flashes a success message and redirects back."""
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if email:
            messages.success(request, f"Thanks — we'll email {email} when we launch.")
    return redirect("pages:coming_soon")


def maintenance(request):
    """Scheduled-downtime page with start + ETA timestamps."""
    started_at = timezone.now() - timedelta(minutes=18)
    expected_at = timezone.now() + timedelta(minutes=42)
    return render(request, "pages/maintenance.html", {
        "started_at": started_at,
        "expected_at": expected_at,
    }, status=503)


def service_unavailable(request):
    """503 page for unexpected outages. Distinct from /maintenance/ —
    that's planned, this is unplanned."""
    return render(request, "pages/service_unavailable.html", {
        "reference": "INC-2026-0042",
    }, status=503)


# ── Showcase galleries ──────────────────────────────────────────────────
# Reference pages that demonstrate form patterns, input states, and
# widget primitives. Pure markup — useful for buyers picking patterns.

@login_required
def forms_gallery(request):
    """Gallery page — instantiates demo forms for each Phase 12 widget so
    the gallery renders real widgets via {% apex_field %}, not static
    HTML mockups.
    """
    from django import forms as _forms

    from apps.core.widgets import (
        Combobox,
        FloatingLabelInput,
        FloatingLabelTextarea,
        IconPrefixInput,
        IconSuffixInput,
        MultiSelect,
        TagInput,
    )

    class _InputsDemoForm(_forms.Form):
        full_name = _forms.CharField(
            label="Full name",
            widget=FloatingLabelInput(floating_label="Full name"),
            help_text="As shown on legal documents.",
        )
        bio = _forms.CharField(
            label="Bio",
            required=False,
            widget=FloatingLabelTextarea(
                floating_label="Bio", rows=3, max_rows=8,
                attrs={"maxlength": "280"},
            ),
            help_text="Up to 280 characters.",
        )
        bio_counter = _forms.CharField(
            label="Bio (with counter)",
            required=False,
            widget=FloatingLabelTextarea(
                floating_label="Bio", rows=3, max_rows=8,
                max_length_counter=True,
                attrs={"maxlength": "140"},
            ),
        )
        search = _forms.CharField(
            label="Search",
            required=False,
            widget=IconPrefixInput(icon="search",
                                   attrs={"placeholder": "Search customers, orders…"}),
        )
        email = _forms.CharField(
            label="Email",
            widget=IconPrefixInput(icon="mail",
                                   attrs={"type": "email",
                                          "placeholder": "you@example.com"}),
        )
        password = _forms.CharField(
            label="Password",
            widget=IconSuffixInput(icon="eye", clickable=True,
                                   attrs={"type": "password"}),
            help_text="Click the eye to show/hide.",
        )

    DEPARTMENTS = (
        ("design", "Design"),
        ("eng", "Engineering"),
        ("marketing", "Marketing"),
        ("sales", "Sales"),
        ("support", "Support"),
        ("ops", "Operations"),
    )

    OWNERS = (
        ("1", "Sara Chen"),
        ("2", "Marcus Patel"),
        ("3", "Jordan Mills"),
        ("4", "Priya Nakamura"),
    )

    class _ChoiceDemoForm(_forms.Form):
        departments = _forms.MultipleChoiceField(
            label="Departments", choices=DEPARTMENTS, required=False,
            widget=MultiSelect(placeholder="Pick teams…"),
            initial=["eng", "design"],
        )
        tags = _forms.CharField(
            label="Tags", required=False,
            widget=TagInput(suggestions=["urgent", "follow-up", "vip", "renewal"],
                            placeholder="Add a tag…"),
            initial="urgent,vip",
        )
        owner = _forms.ChoiceField(
            label="Owner", choices=[("", "")] + list(OWNERS), required=False,
            widget=Combobox(placeholder="Search owners…"),
            initial="1",
        )

    from apps.core.widgets import DateRangePicker, FileDropzone, RichText

    class _DateUploadDemoForm(_forms.Form):
        period = _forms.CharField(
            label="Period", required=False,
            widget=DateRangePicker(),
            initial="2026-04-01,2026-04-30",
            help_text="Stored as a comma-joined ISO range string.",
        )
        attachments = _forms.CharField(
            label="Attachments", required=False,
            widget=FileDropzone(
                upload_url="pages:forms_gallery_upload",
                accept="image/*,.pdf,.csv",
                max_files=5,
                max_size_mb=5,
            ),
            help_text="Files upload via XHR; the field stores comma-joined IDs.",
        )

    class _RichDemoForm(_forms.Form):
        body_basic = _forms.CharField(
            label="Body (basic toolbar)", required=False,
            widget=RichText(toolbar="basic"),
            initial="# Hello\n\nThis is a **markdown** editor.\n\n- Bullet one\n- Bullet two",
        )

    return render(request, "pages/forms_gallery.html", {
        "demo_inputs": _InputsDemoForm(),
        "demo_choice": _ChoiceDemoForm(),
        "demo_date_upload": _DateUploadDemoForm(),
        "demo_rich": _RichDemoForm(),
    })


@login_required
def forms_gallery_upload(request):
    """Demo endpoint backing the forms-gallery FileDropzone widget.

    Accepts a single file at the `file` field (multipart/form-data) and
    returns JSON: `{id, name, size, url}`. The "stored" file is fully
    synthetic — we hash the name to a fake id so the widget can show
    "Uploaded" state without writing to disk. Real applications point
    the dropzone at a view that actually persists the upload (e.g. apps.files).
    """
    import hashlib

    from django.http import HttpResponseBadRequest, JsonResponse
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    f = request.FILES.get("file")
    if not f:
        return HttpResponseBadRequest("No file")
    fake_id = hashlib.sha1(f.name.encode()).hexdigest()[:10]
    return JsonResponse({
        "id": fake_id,
        "name": f.name,
        "size": f.size,
        "url": f"#/demo/{fake_id}",
    })


@login_required
def maps_showcase(request):
    """Geographic visualization demo — customer markers + region density.

    Uses Leaflet (loaded only on this page via head_extra block) with
    OpenStreetMap tiles. No API key required.
    """
    import json as _json

    # Sample customer locations — city, lat, lng, count of customers/MRR.
    locations = [
        {"city": "San Francisco",  "country": "US", "lat": 37.7749,  "lng": -122.4194, "customers": 184, "mrr": 28400},
        {"city": "New York",       "country": "US", "lat": 40.7128,  "lng": -74.0060,  "customers": 312, "mrr": 51800},
        {"city": "Austin",         "country": "US", "lat": 30.2672,  "lng": -97.7431,  "customers": 78,  "mrr": 11200},
        {"city": "London",         "country": "GB", "lat": 51.5074,  "lng": -0.1278,   "customers": 224, "mrr": 38900},
        {"city": "Berlin",         "country": "DE", "lat": 52.5200,  "lng": 13.4050,   "customers": 156, "mrr": 24300},
        {"city": "Amsterdam",      "country": "NL", "lat": 52.3676,  "lng": 4.9041,    "customers": 98,  "mrr": 14600},
        {"city": "Lisbon",         "country": "PT", "lat": 38.7223,  "lng": -9.1393,   "customers": 64,  "mrr": 9200},
        {"city": "Toronto",        "country": "CA", "lat": 43.6532,  "lng": -79.3832,  "customers": 142, "mrr": 21800},
        {"city": "Sydney",         "country": "AU", "lat": -33.8688, "lng": 151.2093,  "customers": 86,  "mrr": 13400},
        {"city": "Tokyo",          "country": "JP", "lat": 35.6762,  "lng": 139.6503,  "customers": 134, "mrr": 22100},
        {"city": "Singapore",      "country": "SG", "lat": 1.3521,   "lng": 103.8198,  "customers": 92,  "mrr": 15800},
        {"city": "Tel Aviv",       "country": "IL", "lat": 32.0853,  "lng": 34.7818,   "customers": 58,  "mrr": 8400},
        {"city": "Buenos Aires",   "country": "AR", "lat": -34.6037, "lng": -58.3816,  "customers": 42,  "mrr": 5200},
        {"city": "São Paulo",      "country": "BR", "lat": -23.5505, "lng": -46.6333,  "customers": 71,  "mrr": 9800},
        {"city": "Mexico City",    "country": "MX", "lat": 19.4326,  "lng": -99.1332,  "customers": 67,  "mrr": 8200},
    ]

    # Top-line stats summed from the dataset
    totals = {
        "customers": sum(p["customers"] for p in locations),
        "mrr":       sum(p["mrr"]       for p in locations),
        "cities":    len(locations),
        "countries": len({p["country"] for p in locations}),
    }

    return render(request, "pages/maps_showcase.html", {
        "locations_json": _json.dumps(locations),
        "locations": locations,
        "totals": totals,
    })


@login_required
def api_docs(request):
    """Single-page API reference. Pure showcase — no models.

    Code samples live here as plain strings rather than inline in the
    template because Django's {% include with %} tag tokenizer can't
    parse multi-line strings with embedded quotes.
    """
    return render(request, "pages/api_docs.html", {
        "base_url": "https://api.apex.example/v1",
        "endpoints": [
            {"method": "GET",    "path": "/customers",            "summary": "List customers"},
            {"method": "POST",   "path": "/customers",            "summary": "Create a customer"},
            {"method": "GET",    "path": "/customers/{id}",       "summary": "Retrieve a customer"},
            {"method": "PATCH",  "path": "/customers/{id}",       "summary": "Update a customer"},
            {"method": "DELETE", "path": "/customers/{id}",       "summary": "Archive a customer"},
            {"method": "GET",    "path": "/orders",               "summary": "List orders"},
            {"method": "POST",   "path": "/orders",               "summary": "Create an order"},
            {"method": "GET",    "path": "/invoices",             "summary": "List invoices"},
            {"method": "POST",   "path": "/invoices/{id}/send",   "summary": "Send an invoice"},
        ],
        "code_auth_curl": (
            "curl https://api.apex.example/v1/customers \\\n"
            "  -H 'Authorization: Bearer apex_pat_a1b2c3d4e5f6...' \\\n"
            "  -H 'Content-Type: application/json'"
        ),
        "code_customers_response": (
            '{\n'
            '  "data": [\n'
            '    {\n'
            '      "id": "cus_a1b2c3",\n'
            '      "name": "Sara Chen",\n'
            '      "email": "sara@northloop.io",\n'
            '      "status": "active",\n'
            '      "created_at": "2026-04-15T10:32:18Z"\n'
            '    }\n'
            '  ],\n'
            '  "page": 1,\n'
            '  "per_page": 20,\n'
            '  "total": 124\n'
            '}'
        ),
        "code_customer_create_curl": (
            "curl -X POST https://api.apex.example/v1/customers \\\n"
            "  -H 'Authorization: Bearer ...' \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\n"
            '    "name": "Sara Chen",\n'
            '    "email": "sara@northloop.io"\n'
            "  }'"
        ),
        "code_orders_python": (
            "import apex\n\n"
            "apex.api_key = 'apex_pat_...'\n\n"
            "order = apex.Order.create(\n"
            "    customer='cus_a1b2c3',\n"
            "    items=[\n"
            "        {'product': 'prod_t8r9', 'quantity': 2, 'price': 49.99},\n"
            "    ],\n"
            "    metadata={'order_source': 'web'},\n"
            ")\n"
            "print(order.id, order.total)"
        ),
        "code_invoice_send_js": (
            "import { Apex } from '@apex/sdk';\n\n"
            "const apex = new Apex({ apiKey: process.env.APEX_KEY });\n\n"
            "await apex.invoices.send('inv_x1y2z3', {\n"
            "  email: 'sara@northloop.io',\n"
            "  cc: ['accounting@northloop.io'],\n"
            "});"
        ),
        "code_webhook_verify": (
            "import hmac, hashlib\n\n"
            "def verify(payload: bytes, signature: str, secret: str) -> bool:\n"
            "    expected = hmac.new(\n"
            "        secret.encode(), payload,\n"
            "        hashlib.sha256,\n"
            "    ).hexdigest()\n"
            "    return hmac.compare_digest(expected, signature)"
        ),
    })


# ── Datatable showcase ──────────────────────────────────────────────────
# Phase 11: the showcase page now links out to the real TableView-powered
# list views (Customers, Orders, Invoices, etc.). Mock data + per-page
# backend gone — all the action is on the actual list pages now.

@login_required
def datatable_demo(request):
    """Showcase page: a links-out grid of every list view powered by TableView."""
    return render(request, "pages/datatable.html", {})


@login_required
def widgets_gallery(request):
    """Curated collection of stat/list/mini-chart/timeline widgets."""
    return render(request, "pages/widgets_gallery.html", {
        # A handful of payloads the template uses to render mini-charts
        # via existing chart factories.
        "stat_cards": [
            {"label": "Revenue", "value": "$48,210", "delta": "+12.4%", "trend": "up",
             "icon": "dollar-sign", "accent": "#16a34a",
             "spark": "[31, 40, 28, 51, 42, 62, 58, 69, 74, 68, 82, 91]"},
            {"label": "New users", "value": "1,284", "delta": "+8.2%", "trend": "up",
             "icon": "users", "accent": "#0891b2",
             "spark": "[12, 18, 14, 22, 30, 28, 35, 32, 41, 47, 52, 58]"},
            {"label": "Conversion", "value": "3.24%", "delta": "+0.4%", "trend": "up",
             "icon": "trending-up", "accent": "#6366f1",
             "spark": "[28, 30, 29, 31, 30, 32, 31, 33, 32, 34, 33, 32]"},
            {"label": "Refund rate", "value": "2.1%", "delta": "-0.3%", "trend": "up",
             "icon": "rotate-ccw", "accent": "#d97706",
             "spark": "[25, 23, 24, 22, 23, 21, 22, 20, 21, 20, 21, 21]"},
        ],
        "leaderboard": [
            {"name": "Sara Chen",     "initials": "SC", "value": "$48.2K", "delta": "+24%"},
            {"name": "Marcus Patel",  "initials": "MP", "value": "$36.1K", "delta": "+18%"},
            {"name": "Laila Okafor",  "initials": "LO", "value": "$29.8K", "delta": "+11%"},
            {"name": "Jordan Mills",  "initials": "JM", "value": "$22.4K", "delta": "+9%"},
            {"name": "Priya Nakamura","initials": "PN", "value": "$18.6K", "delta": "+4%"},
        ],
        "timeline_events": [
            {"icon": "rocket",  "title": "Deployed v2.4.0",         "actor": "Demo User",   "when": "2m ago",  "tone": "primary"},
            {"icon": "check",   "title": "Marked Q1 goals complete","actor": "Sara Chen",   "when": "1h ago",  "tone": "success"},
            {"icon": "user-plus","title":"Added 3 customers",       "actor": "Marcus Patel","when": "3h ago",  "tone": "primary"},
            {"icon": "trash",   "title": "Archived old project",    "actor": "Demo User",   "when": "Yesterday","tone": "muted"},
            {"icon": "trophy",  "title": "Hit MRR target",          "actor": "System",      "when": "2 days ago","tone":"warning"},
        ],
        "progress_targets": [
            {"label": "Q1 revenue", "current": 128430, "target": 150000, "accent": "#16a34a", "is_money": True},
            {"label": "New customers", "current": 347, "target": 500,     "accent": "#0891b2", "is_money": False},
            {"label": "Feature adoption", "current": 62, "target": 80,    "accent": "#6366f1", "is_money": False, "suffix": "%"},
        ],
    })
