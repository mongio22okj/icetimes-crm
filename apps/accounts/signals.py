"""Signal handlers that record AuditEvent rows for built-in Django auth events.

Dashboard-side actions (password change, 2FA toggles, API key creation,
account deletion) call `record_audit` directly from the relevant view.
The user-_logged_in / -_logged_out / -_login_failed signals fire from
inside django.contrib.auth, so we hook them with @receiver instead.
"""
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from apps.accounts.models import record_audit


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    record_audit(user, "login", request=request, description="Signed in")


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    record_audit(user, "logout", request=request, description="Signed out")


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request, **kwargs):
    """Login-failed has no user object; we look it up from credentials
    so we can attribute the failed attempt to the right account.
    Anonymous attempts (unknown username) are dropped — there's nothing
    to attribute and we don't want to leak username existence via the
    audit log either.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    username = (credentials or {}).get("username", "")
    if not username:
        return
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return
    record_audit(user, "login_failed", request=request,
                 description="Failed sign-in attempt")
