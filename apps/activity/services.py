"""Tiny helper for persisting activity events.

Callers (signal handlers, views) use record() to drop a row into
ActivityEvent. Designed to be cheap and never raise — log + swallow on
failure so a misbehaving event source doesn't break the originating
view.
"""
import logging

from .models import ActivityEvent

log = logging.getLogger(__name__)


def record(
    *,
    actor=None,
    category: str = "system",
    verb: str,
    label: str,
    url: str = "",
    icon: str = "",
    metadata: dict | None = None,
) -> ActivityEvent | None:
    try:
        return ActivityEvent.objects.create(
            actor=actor,
            category=category,
            verb=verb,
            label=label,
            url=url or "",
            icon=icon or "",
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("activity.record failed: %s", exc)
        return None
