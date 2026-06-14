"""Public tracking endpoints — no auth required.

Called from external landing pages via JavaScript fetch().
Endpoints:
    POST /api/track/visit/
    POST /api/track/click/
    POST /api/track/lead/
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import LandingClick, LandingVisit, Lead


def _get_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _parse(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


@csrf_exempt
@require_POST
def track_visit(request):
    data = _parse(request)
    LandingVisit.objects.create(
        session_id=data.get("session_id", "")[:255],
        page=data.get("page", "")[:255],
        utm_source=data.get("utm_source", "")[:255] or None,
        utm_campaign=data.get("utm_campaign", "")[:255] or None,
        utm_medium=data.get("utm_medium", "")[:255] or None,
        utm_content=data.get("utm_content", "")[:255] or None,
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def track_click(request):
    data = _parse(request)
    LandingClick.objects.create(
        session_id=data.get("session_id", "")[:255],
        button_name=data.get("button_name", "")[:255],
        page=data.get("page", "")[:255],
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def create_lead(request):
    data = _parse(request)
    email = data.get("email", "").strip()
    if not email:
        return JsonResponse({"status": "error", "message": "email required"}, status=400)

    lead, created = Lead.objects.get_or_create(
        email=email,
        defaults={
            "firstname": data.get("first_name", "")[:120],
            "lastname": data.get("last_name", "")[:120],
            "phone": data.get("phone", "")[:32],
            "source": data.get("source", "landing")[:64],
            "status": "new",
            "payload": data,
        },
    )
    return JsonResponse({
        "status": "ok",
        "lead_id": lead.pk,
        "created": created,
    })
