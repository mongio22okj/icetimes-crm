"""Realtime demo + ad-hoc test-trigger surface.

Two views:

  - `RealtimeDemoView` — `/realtime/` page that opens the presence
    socket, shows live notifications, and lets you fire a test
    notification at yourself for the "open in two tabs" demo.

  - `FireTestNotificationView` — POST endpoint backing the button on
    the demo page. Calls `notify()` for the current user; the dispatch
    hook fans out via the channel layer.
"""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.notifications.dispatch import notify


class RealtimeDemoView(BreadcrumbsMixin, LoginRequiredMixin,
                       EmailVerifiedRequiredMixin, TemplateView):
    template_name = "realtime/demo.html"
    breadcrumb_title = "Realtime"


class FireTestNotificationView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                               View):
    """POST-only — fires a notification at the requesting user."""
    http_method_names = ["post"]

    def post(self, request):
        notify(
            recipient=request.user,
            category="system",
            kind="realtime_demo",
            title="Realtime test notification",
            body=("You should see this appear in every open tab without a "
                  "page refresh — that's the channel layer fanning out."),
            target_url=reverse("realtime:demo"),
        )
        return HttpResponseRedirect(reverse("realtime:demo"))
