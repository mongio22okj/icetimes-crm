"""Auth mixins that slot next to LoginRequiredMixin on protected CBVs."""
from datetime import datetime, timedelta

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme


class EmailVerifiedRequiredMixin:
    """Requires user.email_verified_at is set. Must be paired with
    LoginRequiredMixin (authenticated checks happen there; this mixin only
    enforces verification)."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.email_verified_at is None:
            return redirect("email_verify_prompt")
        return super().dispatch(request, *args, **kwargs)


class PasswordConfirmationRequiredMixin:
    """Re-challenge user's password on sensitive actions. 3-hour grace.

    Place AFTER LoginRequiredMixin in the bases tuple so unauthenticated
    users redirect to login, not to a confirm page they can't reach.
    """
    password_confirmation_max_age = timedelta(hours=3)

    def dispatch(self, request, *args, **kwargs):
        if not self._is_confirmed(request):
            next_url = request.META.get("HTTP_REFERER") or "/"
            # Sanitize so we never forward to an off-host referer
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = "/"
            return redirect(f"{reverse('confirm_password')}?next={next_url}")
        return super().dispatch(request, *args, **kwargs)

    def _is_confirmed(self, request) -> bool:
        stamp = request.session.get("password_confirmed_at")
        if not stamp:
            return False
        try:
            confirmed_at = datetime.fromisoformat(stamp)
        except (ValueError, TypeError):
            return False
        return timezone.now() - confirmed_at < self.password_confirmation_max_age
