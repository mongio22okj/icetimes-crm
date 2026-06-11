"""Phase 17 settings panes — sessions, API tokens, webhooks, audit log,
data export, account deletion.

Lives next to the existing settings views (profile / password / 2FA /
appearance) but in its own module so the file doesn't balloon.
"""
from __future__ import annotations

import io
import json
import zipfile

from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin
from apps.accounts.models import SessionMetadata, record_audit
from apps.api.models import APIKey, Webhook, WebhookDelivery
from apps.core.breadcrumbs import BreadcrumbsMixin
from apps.core.messages import LEVEL_INFO, LEVEL_SUCCESS, toast


class _SettingsBase(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin):
    """Shared base — every settings pane gets the same auth stack."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_tab"] = getattr(self, "active_tab", "")
        return ctx


# ── Sessions ──────────────────────────────────────────────────────────


class SessionsView(_SettingsBase, TemplateView):
    template_name = "settings/sessions.html"
    breadcrumb_title = "Sessions"
    active_tab = "sessions"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Live sessions = SessionMetadata rows whose key is still in
        # django.contrib.sessions.Session. We do the join in Python because
        # the two tables can live in different DBs in some setups.
        live_keys = set(Session.objects.values_list("session_key", flat=True))
        sessions = list(SessionMetadata.objects.filter(
            user=self.request.user, session_key__in=live_keys,
        ))
        current_key = self.request.session.session_key
        for s in sessions:
            s.is_current = (s.session_key == current_key)
        ctx["sessions"] = sessions
        ctx["other_count"] = sum(1 for s in sessions if not s.is_current)
        return ctx


class RevokeSessionView(_SettingsBase, View):
    """Sign out a specific other-than-current session."""
    http_method_names = ["post"]

    def post(self, request, session_key):
        if session_key == request.session.session_key:
            return redirect("settings:sessions")
        meta = get_object_or_404(
            SessionMetadata, session_key=session_key, user=request.user,
        )
        Session.objects.filter(session_key=session_key).delete()
        meta.delete()
        record_audit(request.user, "session_revoked", request=request,
                     description=f"Revoked {meta.device_label()}")
        toast(request, LEVEL_SUCCESS, "Signed out the other device.")
        return redirect("settings:sessions")


class RevokeOtherSessionsView(_SettingsBase, View):
    """Sign out everywhere except the current session."""
    http_method_names = ["post"]

    def post(self, request):
        current_key = request.session.session_key
        keys = list(SessionMetadata.objects.filter(
            user=request.user,
        ).exclude(session_key=current_key).values_list("session_key", flat=True))
        if keys:
            Session.objects.filter(session_key__in=keys).delete()
            SessionMetadata.objects.filter(session_key__in=keys).delete()
            record_audit(request.user, "session_revoked", request=request,
                         description=f"Revoked {len(keys)} other session(s)",
                         metadata={"count": len(keys)})
            toast(request, LEVEL_SUCCESS,
                  f"Signed out {len(keys)} other device{'s' if len(keys) != 1 else ''}.")
        else:
            toast(request, LEVEL_INFO, "No other sessions to sign out.")
        return redirect("settings:sessions")


# ── API tokens ────────────────────────────────────────────────────────


class APITokensView(_SettingsBase, TemplateView):
    template_name = "settings/api_tokens.html"
    breadcrumb_title = "API tokens"
    active_tab = "api_tokens"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tokens"] = list(self.request.user.api_keys.order_by("-created_at"))
        # `just_created` is set in the session by the create view so we
        # can show the raw key exactly once after redirect.
        ctx["just_created_raw"] = self.request.session.pop("api_key_raw", None)
        ctx["just_created_id"] = self.request.session.pop("api_key_id", None)
        return ctx

    def post(self, request, *args, **kwargs):
        name = request.POST.get("name", "").strip() or "Untitled"
        instance, raw = APIKey.generate(request.user, name)
        record_audit(request.user, "api_key_created", request=request,
                     description=f"Created API key '{name}'",
                     metadata={"id": instance.pk, "prefix": instance.key_prefix})
        # Stash for one-shot reveal on the next render. Sessions are
        # signed/encrypted so the raw key isn't world-readable in transit.
        request.session["api_key_raw"] = raw
        request.session["api_key_id"] = instance.pk
        return redirect("settings:api_tokens")


class RevokeAPITokenView(_SettingsBase, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        token = get_object_or_404(APIKey, pk=pk, user=request.user)
        token.revoke()
        record_audit(request.user, "api_key_revoked", request=request,
                     description=f"Revoked API key '{token.name}' ({token.key_prefix}…)",
                     metadata={"id": token.pk})
        toast(request, LEVEL_SUCCESS, f"Revoked '{token.name}'.")
        return redirect("settings:api_tokens")


# ── Webhooks ──────────────────────────────────────────────────────────


# Event names the dashboard currently emits. Surfaced in the UI as a
# checkbox grid so users don't have to know the strings.
WEBHOOK_EVENTS = (
    ("invoice.sent",   "Invoice sent"),
    ("invoice.paid",   "Invoice paid"),
    ("invoice.void",   "Invoice voided"),
    # Future events land here as they're wired into dispatch_webhook calls.
)


class WebhooksView(_SettingsBase, TemplateView):
    template_name = "settings/webhooks.html"
    breadcrumb_title = "Webhooks"
    active_tab = "webhooks"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["webhooks"] = list(
            self.request.user.webhooks.order_by("-created_at"),
        )
        ctx["available_events"] = WEBHOOK_EVENTS
        ctx["just_created_secret"] = self.request.session.pop("webhook_secret", None)
        ctx["just_created_id"] = self.request.session.pop("webhook_id", None)
        # Latest 10 deliveries across all webhooks for this user.
        ctx["recent_deliveries"] = list(
            WebhookDelivery.objects.filter(
                webhook__user=self.request.user,
            ).select_related("webhook").order_by("-created_at")[:10]
        )
        return ctx

    def post(self, request, *args, **kwargs):
        url = request.POST.get("url", "").strip()
        events = request.POST.getlist("events")
        name = request.POST.get("name", "").strip()
        if not url:
            toast(request, LEVEL_INFO, "URL required.")
            return redirect("settings:webhooks")
        if not events:
            toast(request, LEVEL_INFO, "Pick at least one event.")
            return redirect("settings:webhooks")
        w = Webhook.objects.create(
            user=request.user, name=name, url=url,
            events=",".join(events),
            secret=Webhook.generate_secret(),
            is_active=True,
        )
        request.session["webhook_secret"] = w.secret
        request.session["webhook_id"] = w.pk
        return redirect("settings:webhooks")


class DeleteWebhookView(_SettingsBase, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        w = get_object_or_404(Webhook, pk=pk, user=request.user)
        w.delete()
        toast(request, LEVEL_SUCCESS, "Webhook deleted.")
        return redirect("settings:webhooks")


# ── Audit log ─────────────────────────────────────────────────────────


class AuditLogView(_SettingsBase, TemplateView):
    template_name = "settings/audit_log.html"
    breadcrumb_title = "Audit log"
    active_tab = "audit_log"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["events"] = list(
            self.request.user.audit_events.order_by("-created_at")[:200]
        )
        return ctx


# ── Data export ───────────────────────────────────────────────────────


class DataExportView(_SettingsBase, TemplateView):
    template_name = "settings/data_export.html"
    breadcrumb_title = "Export your data"
    active_tab = "data_export"

    def post(self, request, *args, **kwargs):
        record_audit(request.user, "data_export_requested", request=request,
                     description="Requested a data export ZIP")
        # Synchronous export — fine at demo scale. For production swap
        # to a Celery task that emails a download link when ready.
        zip_bytes = build_user_export(request.user)
        response = HttpResponse(zip_bytes, content_type="application/zip")
        response["Content-Disposition"] = (
            f'attachment; filename="apex-export-{request.user.username}.zip"'
        )
        return response


def build_user_export(user) -> bytes:
    """Build a GDPR-shaped JSON ZIP of the user's data.

    One JSON file per resource, all under a top-level folder named after
    the username. Pulls related rows by FK from the user (notifications,
    audit events, API keys, webhooks). Never includes raw API key
    secrets — only the public prefix.
    """
    def _serialize_qs(qs, fields):
        out = []
        for obj in qs:
            row = {}
            for f in fields:
                val = getattr(obj, f, None)
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                row[f] = val
            out.append(row)
        return out

    payload = {
        "user": {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        },
        "notifications": _serialize_qs(
            user.notifications.all(),
            ("id", "category", "kind", "title", "body", "url",
             "read_at", "archived_at", "created_at"),
        ),
        "audit_events": _serialize_qs(
            user.audit_events.all(),
            ("id", "kind", "description", "ip_address", "user_agent",
             "metadata", "created_at"),
        ),
        "api_keys": _serialize_qs(
            user.api_keys.all(),
            ("id", "name", "key_prefix", "last_used_at", "expires_at",
             "revoked_at", "created_at"),
        ),
        "webhooks": _serialize_qs(
            user.webhooks.all(),
            ("id", "name", "url", "events", "is_active", "created_at"),
        ),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for resource, rows in payload.items():
            data = (rows if resource != "user" else rows)
            zf.writestr(
                f"{user.username}/{resource}.json",
                json.dumps(data, indent=2, sort_keys=True, default=str),
            )
        zf.writestr(
            f"{user.username}/README.txt",
            f"Apex data export for {user.username}\n"
            f"Generated: {timezone.now().isoformat()}\n\n"
            "One JSON file per resource. API key secrets are not included — only "
            "the public prefix is exported.\n",
        )
    return buf.getvalue()


# ── Account deletion ──────────────────────────────────────────────────


CONFIRM_PHRASE = "delete my account"


class AccountDeletionView(_SettingsBase, TemplateView):
    template_name = "settings/account_deletion.html"
    breadcrumb_title = "Delete account"
    active_tab = "account_deletion"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["pending"] = self.request.user.is_pending_deletion
        ctx["confirm_phrase"] = CONFIRM_PHRASE
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "request")
        user = request.user
        if action == "cancel":
            if user.is_pending_deletion:
                user.pending_deletion_at = None
                user.save(update_fields=["pending_deletion_at"])
                record_audit(user, "account_deletion_canceled", request=request,
                             description="Cancelled pending account deletion")
                toast(request, LEVEL_SUCCESS, "Pending deletion cancelled.")
            return redirect("settings:account_deletion")
        # Request deletion
        confirm = request.POST.get("confirm", "").strip().lower()
        if confirm != CONFIRM_PHRASE:
            toast(request, LEVEL_INFO, "Confirmation phrase didn't match — nothing changed.")
            return redirect("settings:account_deletion")
        user.pending_deletion_at = timezone.now()
        user.is_active = False
        user.save(update_fields=["pending_deletion_at", "is_active"])
        record_audit(user, "account_deletion_requested", request=request,
                     description="Requested account deletion (30-day grace period)")
        # Sign out — `is_active=False` will block re-login until cancelled.
        auth_logout(request)
        return redirect("login")


