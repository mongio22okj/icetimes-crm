"""Auto-email triggers for "speed-to-lead" (first touchpoint within minutes).

Silently no-ops if Django's email backend is not configured or send_mail
fails — a notification failure must never block lead intake.
"""
import logging
from string import Template

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _render(text, variables):
    """Replace {{var}} tokens — same syntax as the help text in the model."""
    # Convert {{name}} → $name so we can use string.Template safely.
    safe_text = text
    for key in variables:
        safe_text = safe_text.replace("{{" + key + "}}", "$" + key)
    try:
        return Template(safe_text).safe_substitute(variables)
    except Exception:  # noqa: BLE001
        return text


def fire(trigger, lead):
    """Send every active AutoMessage matching `trigger` to lead.email."""
    if not lead.email:
        return
    from .models import AutoMessage

    variables = {
        "firstname": lead.firstname or "",
        "lastname": lead.lastname or "",
        "email": lead.email or "",
        "phone": lead.phone or "",
        "country": (lead.country or "").upper(),
        "status": lead.status or "",
    }
    default_from = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@icetimes.it")
    for msg in AutoMessage.objects.filter(trigger=trigger, is_active=True):
        try:
            send_mail(
                _render(msg.subject, variables),
                _render(msg.body, variables),
                msg.from_email or default_from,
                [lead.email],
                fail_silently=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("AutoMessage %s for lead %s failed: %s", msg.pk, lead.pk, e)
