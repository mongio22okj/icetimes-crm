"""Webhook subscription endpoints — list / create / retrieve / delete.

Scoped to `request.auth_user` so callers only see + manage their own
subscriptions. Creating a webhook returns the secret exactly once;
on subsequent retrievals only the rest of the metadata is exposed.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.models import Webhook
from apps.api.pagination import paginate
from apps.api.schemas import (
    Error,
    WebhookCreated,
    WebhookIn,
    WebhookOut,
    WebhookPage,
)

router = Router()


def _serialize(w: Webhook, *, include_secret: bool = False) -> dict:
    base = {
        "id": w.id,
        "name": w.name,
        "url": w.url,
        "events": sorted(w.event_set()),
        "is_active": w.is_active,
        "created_at": w.created_at,
    }
    if include_secret:
        base["secret"] = w.secret
    return base


@router.get("/", response=WebhookPage, summary="List webhook subscriptions")
def list_webhooks(request, cursor: str = "", limit: int = 25):
    qs = request.auth_user.webhooks.all()
    page = paginate(qs, cursor=cursor or None, limit=limit)
    page["items"] = [_serialize(w) for w in page["items"]]
    return page


@router.post("/", response={201: WebhookCreated, 400: Error},
             summary="Create webhook (returns secret once)")
def create_webhook(request, payload: WebhookIn):
    if not payload.events:
        return 400, {"detail": "events must include at least one event name"}
    w = Webhook.objects.create(
        user=request.auth_user,
        name=payload.name,
        url=payload.url,
        events=",".join(payload.events),
        is_active=payload.is_active,
        secret=Webhook.generate_secret(),
    )
    return 201, _serialize(w, include_secret=True)


@router.get("/{webhook_id}/", response={200: WebhookOut, 404: Error},
            summary="Retrieve webhook")
def get_webhook(request, webhook_id: int):
    w = get_object_or_404(Webhook, pk=webhook_id, user=request.auth_user)
    return _serialize(w)


@router.delete("/{webhook_id}/", response={204: None, 404: Error},
               summary="Delete webhook")
def delete_webhook(request, webhook_id: int):
    w = get_object_or_404(Webhook, pk=webhook_id, user=request.auth_user)
    w.delete()
    return 204, None
