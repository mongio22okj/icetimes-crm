def notification_unread_count(request):
    """Expose current user's unread notification count + recent list to every template.

    Lets the header bell render a correct badge on first paint — before the
    HTMX poll kicks in 30s later. Anonymous users get 0 / empty list.

    The recent list excludes archived notifications (Phase 13) so the bell
    matches the default list view's "Active" scope.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return {"notification_unread_count": 0, "recent_notifications": []}
    active_qs = user.notifications.active()
    return {
        "notification_unread_count": active_qs.unread().count(),
        "recent_notifications": list(active_qs.order_by("-created_at")[:5]),
    }
