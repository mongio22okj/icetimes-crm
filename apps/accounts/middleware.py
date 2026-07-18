"""LockedSessionMiddleware — redirects dashboard routes to /lock/
while the session has `locked = True`. Login/logout/static/landing are
exempt so users can recover.

SessionMetadataMiddleware — populates SessionMetadata for every
authenticated request so /settings/sessions/ can list active sessions
with device + IP + last-seen info. Throttled to one DB write per minute
per session to keep the request hot path cheap.
"""
from django.shortcuts import redirect
from django.utils import timezone

EXEMPT_PREFIXES = (
    "/accounts/login/",
    "/accounts/logout/",
    "/accounts/password-reset/",
    "/lock/",
    "/static/",
    "/landing/",
    "/email/",
)


class LockedSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and request.session.get("locked")
            and not any(request.path.startswith(p) for p in EXEMPT_PREFIXES)
        ):
            return redirect("lock")
        return self.get_response(request)


# Sezioni riservate ad Admin/Marketer: un Visualizzatore che vi accede
# (anche digitando l'URL a mano) viene rediretto alla dashboard. La sidebar
# gli mostra già solo Dashboard + Lead; questo è il rinforzo lato server per
# le aree sensibili (gestione utenti, credenziali broker, dashboard
# finanziaria, admin, fatturazione, azioni di scrittura sui lead).
VIEWER_BLOCKED_PREFIXES = (
    "/users",              # gestione team/utenti
    "/tracking/brokers",   # credenziali broker API
    "/tracking/guida",     # guida operativa (manager/admin)
    "/tracking/sync",      # sync-all
    "/tracking/leads/",    # azioni scrittura sui lead (push/reroute/sync-selected)
    "/dashboards/",        # dashboard CRM finanziaria + varianti
    "/charts",             # grafici/dati finanziari
    "/admin/",             # Django admin
    "/billing",            # abbonamento/fatturazione
    "/orgs",               # organizzazioni
)


class ViewerScopeMiddleware:
    """Confina i Visualizzatori a Dashboard + Lead.

    Un Visualizzatore = utente staff che NON è Super Admin né Marketer
    (role 'staff'). Se prova a raggiungere una sezione riservata
    (VIEWER_BLOCKED_PREFIXES) viene rediretto alla dashboard. Admin e
    Marketer non sono toccati.

    Va dopo AuthenticationMiddleware (usa request.user).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and self._is_viewer(user)
            and request.path.startswith(VIEWER_BLOCKED_PREFIXES)
        ):
            return redirect("dashboard")
        return self.get_response(request)

    @staticmethod
    def _is_viewer(user) -> bool:
        return bool(
            getattr(user, "is_staff", False)
            and not getattr(user, "is_crm_admin", False)
            and not getattr(user, "is_crm_marketer", False)
        )


SESSION_TOUCH_INTERVAL_SECONDS = 60


class SessionMetadataMiddleware:
    """Upsert a SessionMetadata row for the current session.

    Skips: anonymous requests, requests without a session_key, and
    refreshes within SESSION_TOUCH_INTERVAL_SECONDS of the last update
    (tracked via a session key to avoid the DB roundtrip).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_touch(request)
        except Exception:  # noqa: BLE001 — never break the request on bookkeeping
            pass
        return response

    def _maybe_touch(self, request):
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return
        session = getattr(request, "session", None)
        if session is None or not session.session_key:
            return
        last = session.get("_session_meta_touched_at")
        now_ts = int(timezone.now().timestamp())
        if last and (now_ts - last) < SESSION_TOUCH_INTERVAL_SECONDS:
            return
        # Lazy import to avoid circular Django app loading.
        from apps.accounts.models import SessionMetadata
        SessionMetadata.objects.update_or_create(
            session_key=session.session_key,
            defaults={
                "user": user,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:400],
                "ip_address": request.META.get("REMOTE_ADDR") or None,
                "last_seen_at": timezone.now(),
            },
        )
        session["_session_meta_touched_at"] = now_ts


def cleanup_orphan_session_metadata():
    """Drop SessionMetadata rows whose underlying Session is gone.

    Called from a management command (Phase 17 follow-up) or a periodic
    task. Safe to call ad-hoc — it only touches rows whose session_key
    no longer exists in django.contrib.sessions.Session.
    """
    from django.contrib.sessions.models import Session

    from apps.accounts.models import SessionMetadata
    keys_alive = set(Session.objects.values_list("session_key", flat=True))
    stale = SessionMetadata.objects.exclude(session_key__in=keys_alive)
    return stale.delete()[0]


