from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import Broker, Campaign, Click


# ── Track & postback (pubblici) ───────────────────────────────────────────────

@require_GET
def track(request):
    cid = request.GET.get("cid", "")
    if not cid:
        return HttpResponse("cid mancante", status=400)

    campaign = get_object_or_404(Campaign.objects.select_related("broker"), pk=cid)

    click = Click(
        campaign=campaign,
        ip=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        referrer=request.META.get("HTTP_REFERER", ""),
        utm_source=request.GET.get("utm_source") or None,
        utm_medium=request.GET.get("utm_medium") or None,
        utm_campaign=request.GET.get("utm_campaign") or None,
        utm_term=request.GET.get("utm_term") or None,
        utm_content=request.GET.get("utm_content") or None,
    )
    click.save()

    url = campaign.broker.offer_url
    sep = "&" if "?" in url else "?"
    return redirect(f"{url}{sep}subid={click.lead_id}", permanent=False)


@csrf_exempt
@require_GET
def postback(request):
    subid = request.GET.get("subid", "")
    if not subid:
        return HttpResponse("Missing subid", status=400)

    updated = Click.objects.filter(lead_id=subid).update(
        converted=True, conversion_time=timezone.now()
    )
    if not updated:
        return HttpResponse("Lead non trovato", status=404)
    return HttpResponse("OK")


# ── Dashboard (staff only) ────────────────────────────────────────────────────

@login_required
def dashboard(request):
    brokers = Broker.objects.all()
    campaigns = Campaign.objects.select_related("broker").annotate(
        total_clicks=Count("clicks"),
        total_leads=Count("clicks", filter=Q(clicks__converted=True)),
    )
    return render(request, "tracker/dashboard.html", {
        "brokers": brokers,
        "campaigns": campaigns,
        "breadcrumbs": [("Tracker", None)],
    })


@login_required
def report(request, campaign_id):
    campaign = get_object_or_404(Campaign.objects.select_related("broker"), pk=campaign_id)

    qs = Click.objects.filter(campaign=campaign)

    # Filtri UTM
    utm_source = request.GET.get("utm_source", "")
    utm_medium = request.GET.get("utm_medium", "")
    utm_campaign_filter = request.GET.get("utm_campaign", "")
    if utm_source:
        qs = qs.filter(utm_source=utm_source)
    if utm_medium:
        qs = qs.filter(utm_medium=utm_medium)
    if utm_campaign_filter:
        qs = qs.filter(utm_campaign=utm_campaign_filter)

    totals = qs.aggregate(
        clicks=Count("id"),
        leads=Count("id", filter=Q(converted=True)),
        unique_ips=Count("ip", distinct=True),
    )
    cr = round(totals["leads"] / totals["clicks"] * 100, 2) if totals["clicks"] else 0

    by_source = (
        qs.values("utm_source")
        .annotate(clicks=Count("id"), leads=Count("id", filter=Q(converted=True)))
        .order_by("-clicks")
    )
    by_medium = (
        qs.values("utm_medium")
        .annotate(clicks=Count("id"), leads=Count("id", filter=Q(converted=True)))
        .order_by("-clicks")
    )
    by_source_campaign = (
        qs.values("utm_source", "utm_campaign")
        .annotate(
            clicks=Count("id"),
            conversions=Count("id", filter=Q(converted=True)),
        )
        .order_by("-clicks")
    )
    detail = qs.order_by("-click_time")[:200]

    return render(request, "tracker/report.html", {
        "campaign": campaign,
        "totals": totals,
        "cr": cr,
        "by_source": by_source,
        "by_medium": by_medium,
        "by_source_campaign": by_source_campaign,
        "detail": detail,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign_filter,
        "breadcrumbs": [("Tracker", "/tracker/"), (campaign.name, None)],
    })


# ── API per dashboard AJAX ────────────────────────────────────────────────────

@login_required
def api_brokers(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        b = Broker.objects.create(name=data["name"], offer_url=data["offer_url"])
        return JsonResponse({"id": b.pk, "name": b.name, "offer_url": b.offer_url}, status=201)
    brokers = list(Broker.objects.values("id", "name", "offer_url", "created_at"))
    return JsonResponse(brokers, safe=False)


@login_required
def api_broker_delete(request, pk):
    get_object_or_404(Broker, pk=pk).delete()
    return JsonResponse({"ok": True})


@login_required
def api_campaigns(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        c = Campaign.objects.create(name=data["name"], broker_id=data["broker_id"])
        return JsonResponse({"id": c.pk, "name": c.name}, status=201)
    campaigns = Campaign.objects.select_related("broker").annotate(
        total_clicks=Count("clicks"),
        total_leads=Count("clicks", filter=Q(clicks__converted=True)),
    )
    rows = [
        {
            "id": c.pk, "name": c.name, "broker": c.broker.name,
            "clicks": c.total_clicks, "leads": c.total_leads,
            "cr": round(c.total_leads / c.total_clicks * 100, 2) if c.total_clicks else 0,
        }
        for c in campaigns
    ]
    return JsonResponse(rows, safe=False)


@login_required
def api_campaign_delete(request, pk):
    get_object_or_404(Campaign, pk=pk).delete()
    return JsonResponse({"ok": True})
