"""High-level sync service — wraps sync.py and writes SyncAudit rows."""
import logging

from .models import SyncAudit
from .sync import run_all_sources

logger = logging.getLogger(__name__)


def run_sync(dry_run: bool = False) -> dict:
    """Run lead sync across all active sources and log the result.

    Returns a dict with keys: ok (list), errors (list), audit_id (int).
    """
    if dry_run:
        logger.info("Dry-run: skip actual sync")
        audit = SyncAudit.objects.create(action="sync", details="dry_run=True")
        return {"ok": [], "errors": [], "audit_id": audit.pk, "dry_run": True}

    ok, errors = run_all_sources()

    details_lines = [f"ok: {', '.join(ok)}"] if ok else []
    if errors:
        details_lines.append(f"errors: {', '.join(errors)}")

    audit = SyncAudit.objects.create(
        action="sync" if not errors else "error",
        details="\n".join(details_lines),
    )

    logger.info("Sync completed: %d ok, %d errors", len(ok), len(errors))
    return {"ok": ok, "errors": errors, "audit_id": audit.pk, "dry_run": False}


def get_sync_status() -> dict:
    """Return status of the last sync audit."""
    last = SyncAudit.objects.first()
    if not last:
        return {"last_sync": None, "last_action": None, "details": ""}
    return {
        "last_sync": last.timestamp.isoformat(),
        "last_action": last.action,
        "source": last.source,
        "details": last.details,
    }
