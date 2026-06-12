"""Resolve which lead sources are active.

Single source of truth = the LeadSource DB table (managed from the UI).
For backward compatibility, when the table has no active row of a given
kind we synthesize an in-memory source from the legacy environment
variables so existing deployments keep working until seeded.
"""
from types import SimpleNamespace

from django.conf import settings

from .models import LeadSource


def _env_shim(kind, **fields):
    """Build an unsaved LeadSource-like object from env values."""
    base = dict(
        pk=None, name=f"{kind} (env)", kind=kind, is_active=True,
        base_url="", token="", username="", password="",
        ai="", ci="1", gi="", affiliate_id="", offer_id="",
        goal_lead="", goal_ftd="",
    )
    base.update(fields)
    obj = SimpleNamespace(**base)
    obj.can_pull = kind in LeadSource.PULL_KINDS
    obj.can_push = kind in LeadSource.PUSH_KINDS
    obj.slug = kind
    return obj


def _env_sources():
    shims = []
    if settings.TRACKBOX_BASE_URL and settings.TRACKBOX_API_KEY:
        shims.append(_env_shim(
            LeadSource.KIND_TRACKBOX, name="TrackBox (env)",
            base_url=settings.TRACKBOX_BASE_URL, token=settings.TRACKBOX_API_KEY,
            username=settings.TRACKBOX_USERNAME, password=settings.TRACKBOX_PASSWORD,
            ai=settings.TRACKBOX_AI, ci=settings.TRACKBOX_CI, gi=settings.TRACKBOX_GI,
        ))
    if settings.IREV_BASE_URL and settings.IREV_TOKEN:
        shims.append(_env_shim(
            LeadSource.KIND_IREV, name="IREV (env)",
            base_url=settings.IREV_BASE_URL, token=settings.IREV_TOKEN,
            affiliate_id=settings.IREV_AFFILIATE_ID, offer_id=settings.IREV_OFFER_ID,
            goal_lead=settings.IREV_GOAL_LEAD, goal_ftd=settings.IREV_GOAL_FTD,
        ))
    if settings.AFFINITRAX_BASE_URL and settings.AFFINITRAX_API_KEY:
        shims.append(_env_shim(
            LeadSource.KIND_AFFINITRAX, name="Affinitrax (env)",
            base_url=settings.AFFINITRAX_BASE_URL, token=settings.AFFINITRAX_API_KEY,
        ))
    return shims


def active_sources():
    """Return active LeadSource rows; fall back to env shims per missing kind."""
    db_rows = list(LeadSource.objects.filter(is_active=True))
    db_kinds = {s.kind for s in db_rows}
    result = list(db_rows)
    for shim in _env_sources():
        if shim.kind not in db_kinds:
            result.append(shim)
    return result


def push_sources():
    return [s for s in active_sources() if s.can_push]


def resolve(token):
    """Map a form 'target' value back to its active source object."""
    if not token:
        return None
    for src in active_sources():
        ident = str(src.pk) if getattr(src, "pk", None) else f"env-{src.kind}"
        if ident == str(token):
            return src
    return None
