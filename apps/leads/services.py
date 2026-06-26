"""Stub sync service — broker API integration rimossa."""
import logging

from .models import SyncAudit

logger = logging.getLogger(__name__)


def run_sync(dry_run: bool = False) -> dict:
    audit = SyncAudit.objects.create(action="sync", details="nessun broker configurato")
    return {"ok": [], "errors": [], "audit_id": audit.pk, "dry_run": dry_run}


def get_sync_status() -> dict:
    last = SyncAudit.objects.first()
    if not last:
        return {"last_sync": None, "last_action": None, "details": ""}
    return {
        "last_sync": last.timestamp.isoformat(),
        "last_action": last.action,
        "source": last.source,
        "details": last.details,
    }
