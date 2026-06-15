"""Public tracking endpoints — no auth required.

Called from external landing pages via JavaScript fetch().
Endpoints:
    POST /api/track/visit/
    POST /api/track/click/
    POST /api/track/lead/
"""
import json
import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import LandingClick, LandingVisit, Lead

# Un "source" è un identificatore, non testo libero: teniamo solo
# caratteri sicuri (no '<', '>', '/', '"', ecc.) per evitare che il
# valore venga usato come vettore in viste a valle.
_SOURCE_SANITIZE = re.compile(r"[^\w.\-: ]+")


def _s(value, limit: int | None = None) -> str:
    """Coerce qualsiasi valore JSON a stringa (un broker può mandare
    numeri/null), poi opzionalmente tronca. Evita TypeError su slicing."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text[:limit] if limit else text


def _clean_source(value, default: str = "landing") -> str:
    cleaned = _SOURCE_SANITIZE.sub("", _s(value))[:64].strip()
    return cleaned or default


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
        session_id=_s(data.get("session_id"), 255),
        page=_s(data.get("page"), 255),
        utm_source=_s(data.get("utm_source"), 255) or None,
        utm_campaign=_s(data.get("utm_campaign"), 255) or None,
        utm_medium=_s(data.get("utm_medium"), 255) or None,
        utm_content=_s(data.get("utm_content"), 255) or None,
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def track_click(request):
    data = _parse(request)
    LandingClick.objects.create(
        session_id=_s(data.get("session_id"), 255),
        button_name=_s(data.get("button_name"), 255),
        page=_s(data.get("page"), 255),
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def create_lead(request):
    data = _parse(request)
    email = _s(data.get("email")).strip().lower()
    if not email:
        return JsonResponse({"status": "error", "message": "email required"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"status": "error", "message": "invalid email"}, status=400)

    lead, created = Lead.objects.get_or_create(
        email=email,
        defaults={
            "firstname": _s(data.get("first_name"), 120),
            "lastname": _s(data.get("last_name"), 120),
            "phone": _s(data.get("phone"), 32),
            "source": _clean_source(data.get("source"), "landing"),
            "status": "new",
            "payload": data if isinstance(data, dict) else {},
        },
    )

    # Speed-to-lead: notifica istantanea (Slack/Telegram/…) sui lead nuovi.
    if created:
        try:
            from . import notifications
            notifications.fire("new_lead", {
                "name": lead.full_name or "—",
                "email": lead.email,
                "phone": lead.phone,
                "country": lead.country,
                "source": lead.source,
                "score": lead.score,
            })
        except Exception:  # noqa: BLE001
            pass

    return JsonResponse({
        "status": "ok",
        "lead_id": lead.pk,
        "created": created,
    })
