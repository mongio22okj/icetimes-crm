"""Public tracking endpoints — no auth required.

Called from external landing pages via JavaScript fetch().
Endpoints:
    POST /api/track/visit/
    POST /api/track/click/
    POST /api/track/lead/
"""
import json
import re
from functools import wraps
from urllib.parse import urlencode, urlparse, urlunparse

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import LandingClick, LandingVisit, Lead, LeadSource, TrackingLink


def cors_public(view):
    """Permette di chiamare l'endpoint da qualsiasi dominio (landing esterne).
    Gestisce il preflight OPTIONS e aggiunge gli header CORS alla risposta."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == "OPTIONS":
            resp = HttpResponse(status=204)
        else:
            resp = view(request, *args, **kwargs)
        resp["Access-Control-Allow-Origin"] = "*"
        resp["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        resp["Access-Control-Allow-Headers"] = "Content-Type"
        resp["Access-Control-Max-Age"] = "86400"
        return resp
    return wrapped


def _first(data, *keys):
    """Primo valore non vuoto tra una lista di nomi-campo alternativi."""
    for k in keys:
        v = data.get(k)
        if v not in (None, ""):
            return v
    return ""

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


def tracking_redirect(request, code):
    """`/t/<code>/` — registra il click e reindirizza alla destinazione."""
    link = TrackingLink.objects.filter(code=code, is_active=True).first()
    if link is None:
        raise Http404()

    # Log click come visita (riusa LandingVisit), con UTM dal query string.
    q = request.GET
    LandingVisit.objects.create(
        session_id=_s(q.get("sid"), 255) or f"t-{code}",
        page=f"/t/{code}/",
        utm_source=_s(q.get("utm_source"), 255) or None,
        utm_campaign=_s(q.get("utm_campaign"), 255) or None,
        utm_medium=_s(q.get("utm_medium"), 255) or None,
        utm_content=_s(q.get("utm_content"), 255) or None,
        ip=_get_ip(request),
    )
    TrackingLink.objects.filter(pk=link.pk).update(clicks=F("clicks") + 1)

    # Aggiunge cid=<code> alla destinazione (per matchare il postback) e
    # click_id=<code> per l'attribuzione lato affiliate (es. funnel IREV).
    # Un click_id esplicito nel query string vince (override manuale),
    # altrimenti usiamo il codice del link. Preserva gli UTM in arrivo.
    parts = urlparse(link.destination)
    params = dict(p.split("=", 1) for p in parts.query.split("&") if "=" in p)
    params["cid"] = code
    params["click_id"] = q.get("click_id") or code
    # IREV richiede il nostro click id nel campo aff_sub5: lo rimanda nel
    # postback per agganciare il lead al click.
    params["aff_sub5"] = q.get("aff_sub5") or q.get("click_id") or code
    for k in ("utm_source", "utm_campaign", "utm_medium", "utm_content"):
        if q.get(k):
            params[k] = q.get(k)
    dest = urlunparse(parts._replace(query=urlencode(params)))
    return redirect(dest)


@csrf_exempt
@cors_public
@require_POST
def track_visit(request):
    data = _parse(request)
    LandingVisit.objects.create(
        session_id=_s(_first(data, "session_id", "sid"), 255),
        page=_s(data.get("page"), 255),
        utm_source=_s(_first(data, "utm_source", "source"), 255) or None,
        utm_campaign=_s(_first(data, "utm_campaign", "campaign"), 255) or None,
        utm_medium=_s(data.get("utm_medium"), 255) or None,
        utm_content=_s(data.get("utm_content"), 255) or None,
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


@csrf_exempt
@cors_public
@require_POST
def track_click(request):
    data = _parse(request)
    LandingClick.objects.create(
        session_id=_s(_first(data, "session_id", "sid"), 255),
        button_name=_s(_first(data, "button_name", "button"), 255),
        page=_s(data.get("page"), 255),
        ip=_get_ip(request),
    )
    return JsonResponse({"status": "ok"})


def _split_name(full):
    """Divide 'Mario Rossi' in (Mario, Rossi). Un solo nome → resta tutto first."""
    parts = _s(full).strip().split(None, 1)
    if not parts:
        return "", ""
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _resolve_broker(data):
    """Trova il broker destinatario da cid (codice link) o broker_id (pk)."""
    cid = _s(_first(data, "cid", "tracking_code"))
    if cid:
        tl = (TrackingLink.objects.filter(code=cid)
              .select_related("source").first())
        if tl and tl.source:
            return tl.source
    bid = _s(_first(data, "broker_id", "source_id"))
    if bid.isdigit():
        return LeadSource.objects.filter(pk=int(bid), is_active=True).first()
    return None


@csrf_exempt
@cors_public
@require_POST
def create_lead(request):
    data = _parse(request)
    if not isinstance(data, dict):
        data = {}
    email = _s(_first(data, "email", "mail")).strip().lower()
    if not email:
        return JsonResponse({"status": "error", "message": "email required"}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"status": "error", "message": "invalid email"}, status=400)

    # #2 Alias campi: accetta first_name/nome, last_name/cognome, phone/telefono.
    firstname = _s(_first(data, "first_name", "firstname", "nome"), 120)
    lastname = _s(_first(data, "last_name", "lastname", "cognome"), 120)
    if not firstname and not lastname:
        firstname, lastname = _split_name(_first(data, "name", "full_name"))
        firstname, lastname = firstname[:120], lastname[:120]
    phone = _s(_first(data, "phone", "telefono", "phone_number"), 32)

    # #3 broker_id routing: il lead può arrivare già destinato a un broker.
    broker = _resolve_broker(data)
    source = broker.slug if broker else _clean_source(
        _first(data, "source", "utm_source"), "landing")

    try:
        lead, created = Lead.objects.get_or_create(
            email=email,
            defaults={
                "firstname": firstname,
                "lastname": lastname,
                "phone": phone,
                "source": source,
                "status": "new",
                "payload": data,
            },
        )
    except Lead.MultipleObjectsReturned:
        # Lead.email NON è univoca: se esistono già più righe con questa email
        # (storico o submission concorrenti) get_or_create solleverebbe 500.
        # Riusa la più recente invece di esplodere.
        lead = Lead.objects.filter(email=email).order_by("-created_at").first()
        created = False

    if created:
        # Speed-to-lead: notifica istantanea sui lead nuovi.
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
        # #3 Dispatch immediato al broker destinatario, se indicato.
        if broker is not None:
            try:
                from . import dispatch as _dispatch
                _dispatch.dispatch(lead, sources=[broker])
            except Exception:  # noqa: BLE001
                pass

    return JsonResponse({
        "status": "ok",
        "lead_id": lead.pk,
        "created": created,
        "broker": broker.name if broker else None,
    })
