"""Notification surfaces — list page, bell partial, action endpoints,
preferences page, push subscription endpoints.
"""
from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.notifications.models import (
    CATEGORY_CHOICES,
    CHANNELS,
    Notification,
    NotificationPreference,
    PushSubscription,
)


def _is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _bell_context(user) -> dict:
    return {
        "recent_notifications": list(
            user.notifications.active().order_by("-created_at")[:5]
        ),
        "notification_unread_count": user.notifications.unread().count(),
    }


class NotificationListView(BreadcrumbsMixin, LoginRequiredMixin,
                            EmailVerifiedRequiredMixin, ListView):
    paginate_by = 20
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    breadcrumb_title = "Notifications"

    def get_queryset(self):
        qs = self.request.user.notifications.select_related("actor")
        scope = self.request.GET.get("scope", "active")
        if scope == "archived":
            qs = qs.archived()
        else:
            qs = qs.active()
        category = self.request.GET.get("category", "")
        if category:
            qs = qs.for_category(category)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["category"] = self.request.GET.get("category", "")
        ctx["scope"] = self.request.GET.get("scope", "active")
        ctx["category_choices"] = CATEGORY_CHOICES
        # Group by date bucket for the "Today / Yesterday / Earlier" headers.
        today = timezone.localdate()
        groups: OrderedDict[str, list] = OrderedDict()
        for n in ctx["notifications"]:
            d = timezone.localtime(n.created_at).date()
            if d == today:
                bucket = "Today"
            elif (today - d).days == 1:
                bucket = "Yesterday"
            elif (today - d).days < 7:
                bucket = "Earlier this week"
            elif (today - d).days < 30:
                bucket = "Earlier this month"
            else:
                bucket = "Older"
            groups.setdefault(bucket, []).append(n)
        ctx["grouped"] = list(groups.items())
        # Counts shown in the filter pills.
        active_qs = self.request.user.notifications.active()
        ctx["counts"] = {"all": active_qs.count(), "unread": active_qs.unread().count()}
        ctx["counts_by_category"] = {
            key: active_qs.for_category(key).count() for key, _label in CATEGORY_CHOICES
        }
        return ctx


class BellView(LoginRequiredMixin, View):
    """HTMX partial rendering unread count + 5 most recent notifications."""
    http_method_names = ["get"]

    def get(self, request):
        return render(request, "notifications/_bell.html", _bell_context(request.user))


class MarkReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, recipient=request.user,
        )
        notification.mark_read()
        if _is_htmx(request):
            return render(request, "notifications/_bell.html", _bell_context(request.user))
        return redirect(notification.url or "notifications:list")


class MarkAllReadView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        count = (request.user.notifications.unread()
                 .update(read_at=timezone.now()))
        if _is_htmx(request):
            return render(request, "notifications/_bell.html", _bell_context(request.user))
        if count:
            messages.success(
                request, f"Marked {count} notification{'s' if count != 1 else ''} as read.",
            )
        return redirect("notifications:list")


class ArchiveView(LoginRequiredMixin, View):
    """Archive a single notification (or restore via ?action=restore)."""
    http_method_names = ["post"]

    def post(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, recipient=request.user,
        )
        if request.POST.get("action") == "restore":
            notification.archived_at = None
            notification.save(update_fields=["archived_at"])
        else:
            notification.archive()
        return redirect(request.META.get("HTTP_REFERER") or "notifications:list")


# ── Preferences ────────────────────────────────────────────────────────


class PreferencesView(BreadcrumbsMixin, LoginRequiredMixin,
                      EmailVerifiedRequiredMixin, TemplateView):
    template_name = "notifications/preferences.html"
    breadcrumb_title = "Preferences"
    breadcrumb_parent = "notifications:list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.notifications.models import CHANNEL_DEFAULTS
        prefs = {p.category: p for p in NotificationPreference.objects.filter(
            user=self.request.user,
        )}
        rows = []
        for key, label in CATEGORY_CHOICES:
            pref = prefs.get(key)
            defaults = CHANNEL_DEFAULTS.get(key, {})
            rows.append({
                "key": key,
                "label": label,
                "in_app": pref.in_app if pref else defaults.get("in_app", True),
                "email": pref.email if pref else defaults.get("email", False),
                "push": pref.push if pref else defaults.get("push", False),
            })
        ctx["rows"] = rows
        ctx["channels"] = CHANNELS
        ctx["push_count"] = self.request.user.push_subscriptions.count()
        return ctx

    def post(self, request, *args, **kwargs):
        for key, _label in CATEGORY_CHOICES:
            updates = {ch: request.POST.get(f"{key}__{ch}") == "on" for ch in CHANNELS}
            NotificationPreference.objects.update_or_create(
                user=request.user, category=key, defaults=updates,
            )
        messages.success(request, "Notification preferences saved.")
        return redirect("notifications:preferences")


# ── Push subscription endpoints ───────────────────────────────────────


class PushSubscribeView(LoginRequiredMixin, View):
    """Register a Web Push subscription. Browser POSTs JSON:

        {"endpoint": "...", "keys": {"p256dh": "...", "auth": "..."}}
    """
    http_method_names = ["post"]

    def post(self, request):
        import json as _json
        try:
            data = _json.loads(request.body)
        except _json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
        endpoint = data.get("endpoint", "").strip()
        keys = data.get("keys") or {}
        p256dh = keys.get("p256dh", "")
        auth = keys.get("auth", "")
        if not endpoint or not p256dh or not auth:
            return HttpResponseBadRequest("Missing endpoint or keys")
        sub, _ = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
            },
        )
        return JsonResponse({"id": sub.pk, "ok": True})


class PushUnsubscribeView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        import json as _json
        try:
            data = _json.loads(request.body)
        except _json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON")
        endpoint = data.get("endpoint", "").strip()
        if not endpoint:
            return HttpResponseBadRequest("Missing endpoint")
        deleted, _ = PushSubscription.objects.filter(
            user=request.user, endpoint=endpoint,
        ).delete()
        return JsonResponse({"deleted": deleted, "ok": True})
