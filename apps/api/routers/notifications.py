"""Notifications endpoints — list / read / archive (current user only).

Scoped to `request.auth_user` — the API key's owner — so each caller
sees only their own notifications, never others'.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from ninja import Router

from apps.api.pagination import paginate
from apps.api.schemas import Error, NotificationOut, NotificationPage
from apps.notifications.models import Notification

router = Router()


@router.get("/", response=NotificationPage, summary="List notifications")
def list_notifications(
    request,
    category: str = "",
    unread: bool = False,
    archived: bool = False,
    cursor: str = "",
    limit: int = 25,
):
    user = request.auth_user
    qs = user.notifications.archived() if archived else user.notifications.active()
    if category:
        qs = qs.for_category(category)
    if unread:
        qs = qs.unread()
    return paginate(qs, cursor=cursor or None, limit=limit)


@router.post("/{notification_id}/read/", response={200: NotificationOut, 404: Error},
             summary="Mark notification read")
def mark_read(request, notification_id: int):
    n = get_object_or_404(
        Notification, pk=notification_id, recipient=request.auth_user,
    )
    n.mark_read()
    return n


@router.post("/read-all/", response={200: dict}, summary="Mark every unread notification read")
def mark_all_read(request):
    from django.utils import timezone
    n = (request.auth_user.notifications.unread()
         .update(read_at=timezone.now()))
    return 200, {"marked_read": n}


@router.post("/{notification_id}/archive/", response={200: NotificationOut, 404: Error},
             summary="Archive notification")
def archive(request, notification_id: int):
    n = get_object_or_404(
        Notification, pk=notification_id, recipient=request.auth_user,
    )
    n.archive()
    n.refresh_from_db()
    return n
