"""Sync endpoints — trigger and status for lead synchronisation."""
from __future__ import annotations

from typing import Optional
from ninja import Router, Schema

from apps.leads.services import get_sync_status, run_sync

router = Router()


class SyncTriggerIn(Schema):
    dry_run: bool = False


class SyncResultOut(Schema):
    success: bool
    ok: list[str]
    errors: list[str]
    audit_id: int
    dry_run: bool


class SyncStatusOut(Schema):
    last_sync: Optional[str]
    last_action: Optional[str]
    source: Optional[str] = None
    details: str


@router.post("/trigger/", response=SyncResultOut, summary="Avvia sync leads")
def trigger_sync(request, payload: SyncTriggerIn = SyncTriggerIn()):
    result = run_sync(dry_run=payload.dry_run)
    return {
        "success": len(result["errors"]) == 0,
        **result,
    }


@router.get("/status/", response=SyncStatusOut, summary="Stato ultima sync")
def sync_status(request):
    return get_sync_status()
