import io
from datetime import datetime

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import PasswordChangeView as DjangoPasswordChangeView
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView

from apps.accounts.mixins import EmailVerifiedRequiredMixin, PasswordConfirmationRequiredMixin
from apps.core.breadcrumbs import BreadcrumbsMixin

from .forms import (
    PasswordConfirmForm,
    ProfileForm,
    RegisterForm,
    StyledPasswordChangeForm,
    TwoFactorChallengeForm,
    TwoFactorSetupForm,
    UserCreateForm,
    UserUpdateForm,
)
from .models import User
from .two_factor import TwoFactorDevice
from .verify_email import send_verify_email


class RegisterView(View):
    """Registrazione pubblica. Chiusa di default: gli account li crea solo
    l'amministratore (pagina Users / admin). Riapribile con
    settings.ALLOW_PUBLIC_REGISTRATION = True."""

    def _check_open(self, request):
        if not getattr(settings, "ALLOW_PUBLIC_REGISTRATION", False):
            messages.info(
                request,
                "La registrazione è chiusa. Gli account vengono creati "
                "dall'amministratore: contattalo per ottenere l'accesso.")
            return redirect("login")
        return None

    def get(self, request):
        return self._check_open(request) or render(
            request, "accounts/register.html", {"form": RegisterForm()})

    def post(self, request):
        closed = self._check_open(request)
        if closed:
            return closed
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            send_verify_email(user, request)
            request.session["verify_email_sent_at"] = timezone.now().isoformat()
            return redirect("email_verify_prompt")
        return render(request, "accounts/register.html", {"form": form})


class StaffRequiredMixin(UserPassesTestMixin):
    """Require request.user.is_staff for access.
    - Unauthenticated users: 302 redirect to login.
    - Authenticated non-staff: 403 Forbidden.
    """
    raise_exception = True

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(self.request.get_full_path())
        return super().handle_no_permission()


from apps.core.messages import LEVEL_SUCCESS  # noqa: E402
from apps.core.messages import toast as toast_message  # noqa: E402
from apps.core.tables import (  # noqa: E402
    BulkAction,
    Column,
    Filter,
    TableConfig,
    TableView,
)

USERS_TABLE = TableConfig(
    key="users",
    bulk_actions=(
        BulkAction(slug="activate", label="Consenti accesso", icon="check"),
        BulkAction(slug="deactivate", label="Blocca accesso", icon="x", destructive=True,
                   confirm_text="Bloccare l'accesso a {n} utenti? Non potranno più entrare."),
    ),
    columns=(
        Column("username", "User", searchable=True, pinned=True,
               template="accounts/_table_cells.html#user"),
        Column("email", "Email", searchable=True, priority=2,
               filter=Filter("text", placeholder="Filter email…")),
        Column("role", "Role",
               filter=Filter("select", choices=User.ROLE_CHOICES),
               template="accounts/_table_cells.html#role"),
        Column("is_active", "Accesso",
               filter=Filter("boolean"), align="center",
               formatter=lambda v: "Consentito" if v else "In attesa"),
        Column("date_joined", "Joined",
               sortable=True, filter=Filter("daterange"), priority=2,
               formatter=lambda v: v.strftime("%b %d, %Y") if v else ""),
    ),
    default_sort="-date_joined",
    page_size=25,
    sticky_first=True,
    caption="Manage staff and roles.",
)


class UserListView(BreadcrumbsMixin, LoginRequiredMixin,
                   EmailVerifiedRequiredMixin, StaffRequiredMixin, TableView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    breadcrumb_title = "Users"
    table_config = USERS_TABLE

    def handle_bulk_action(self, action, ids, request):
        targets = User.objects.filter(pk__in=ids)
        n = targets.count()
        if action.slug == "activate":
            targets.update(is_active=True)
            toast_message(request, LEVEL_SUCCESS, f"Accesso consentito a {n} utenti.")
        elif action.slug == "deactivate":
            # Don't lock yourself out.
            targets.exclude(pk=request.user.pk).update(is_active=False)
            toast_message(request, LEVEL_SUCCESS, f"Accesso bloccato per {n} utenti.")
        return redirect("users:list")


class UserDetailView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, StaffRequiredMixin, DetailView):
    model = User
    template_name = "accounts/user_detail.html"
    context_object_name = "target_user"  # avoid clobbering 'user' context
    breadcrumb_parent = "users:list"

    def get_breadcrumb_title(self):
        return self.object.username


class UserAccessToggleView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           StaffRequiredMixin, View):
    """Dà o toglie l'OK all'accesso di un utente (is_active). Solo staff."""

    def post(self, request, pk):
        target = get_object_or_404(User, pk=pk)
        if target.pk == request.user.pk:
            messages.error(request, "Non puoi bloccare il tuo stesso account.")
            return redirect("users:detail", pk=pk)
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        if target.is_active:
            messages.success(request, f"Accesso CONSENTITO a {target.username}.")
        else:
            messages.success(request, f"Accesso BLOCCATO per {target.username}.")
        return redirect("users:detail", pk=pk)


class UserCreateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, StaffRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("users:list")
    breadcrumb_title = "New user"
    breadcrumb_parent = "users:list"


class UserUpdateView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, StaffRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("users:list")
    context_object_name = "target_user"
    breadcrumb_parent = "users:list"

    def get_breadcrumb_title(self):
        return f"Edit {self.object.username}"


class ProfileView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, UpdateView):
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("settings:profile")
    breadcrumb_title = "Settings"
    extra_context = {"active_tab": "profile"}

    def get_object(self, queryset=None):
        return self.request.user


class PasswordChangeView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, DjangoPasswordChangeView):
    form_class = StyledPasswordChangeForm
    template_name = "settings/password.html"
    success_url = reverse_lazy("settings:password")
    breadcrumb_title = "Settings"
    extra_context = {"active_tab": "password"}


class AppearanceView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, TemplateView):
    template_name = "settings/appearance.html"
    breadcrumb_title = "Settings"
    extra_context = {"active_tab": "appearance"}


class TwoFactorView(BreadcrumbsMixin, LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    breadcrumb_title = "Settings"

    def get(self, request):
        device = TwoFactorDevice.objects.filter(user=request.user).first()
        # Recovery codes are one-shot: rendered then cleared from session.
        flash_codes = request.session.pop("_2fa_recovery_codes", None)
        return render(request, "settings/two_factor.html", {
            "device": device,
            "confirmed": device.confirmed if device else False,
            "has_unconfirmed": bool(device and not device.confirmed),
            "enable_form": PasswordConfirmForm(user=request.user),
            "disable_form": PasswordConfirmForm(user=request.user),
            "flash_codes": flash_codes,
            "active_tab": "two_factor",
        })


class TwoFactorEnableView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def post(self, request):
        # Refuse if already confirmed — prevents password-only attacker from wiping 2FA.
        if TwoFactorDevice.objects.filter(user=request.user, confirmed=True).exists():
            return redirect("settings:two_factor")
        form = PasswordConfirmForm(request.POST, user=request.user)
        if form.is_valid():
            TwoFactorDevice.create_unconfirmed(request.user)
            return redirect("settings:two_factor_setup")
        messages.error(request, "Password incorrect.")
        return redirect("settings:two_factor")


class TwoFactorSetupView(LoginRequiredMixin, EmailVerifiedRequiredMixin, View):
    def _get_unconfirmed(self, request):
        return TwoFactorDevice.objects.filter(user=request.user, confirmed=False).first()

    def get(self, request):
        device = self._get_unconfirmed(request)
        if not device:
            return redirect("settings:two_factor")
        qr_svg = self._render_qr(device.provisioning_uri())
        return render(request, "settings/two_factor_setup.html", {
            "device": device,
            "qr_svg": qr_svg,
            "form": TwoFactorSetupForm(),
            "active_tab": "two_factor",
        })

    def post(self, request):
        device = self._get_unconfirmed(request)
        if not device:
            return redirect("settings:two_factor")
        form = TwoFactorSetupForm(request.POST)
        if form.is_valid() and device.verify_totp(form.cleaned_data["code"]):
            device.confirmed = True
            device.confirmed_at = timezone.now()
            device.save(update_fields=["confirmed", "confirmed_at"])
            codes = device.generate_recovery_codes()
            request.session["_2fa_recovery_codes"] = codes
            return redirect("settings:two_factor")
        form.add_error("code", "Invalid code. Check your authenticator and try again.")
        qr_svg = self._render_qr(device.provisioning_uri())
        return render(request, "settings/two_factor_setup.html", {
            "device": device, "qr_svg": qr_svg, "form": form,
            "active_tab": "two_factor",
        })

    @staticmethod
    def _render_qr(uri: str) -> str:
        factory = qrcode.image.svg.SvgPathImage
        img = qrcode.make(uri, image_factory=factory, box_size=10, border=2)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode()


class TwoFactorDisableView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                           PasswordConfirmationRequiredMixin, View):
    def post(self, request):
        TwoFactorDevice.objects.filter(user=request.user).delete()
        messages.success(request, "Two-factor authentication disabled.")
        return redirect("settings:two_factor")


class TwoFactorRegenerateView(LoginRequiredMixin, EmailVerifiedRequiredMixin,
                              PasswordConfirmationRequiredMixin, View):
    def post(self, request):
        device = TwoFactorDevice.objects.filter(user=request.user, confirmed=True).first()
        if device:
            codes = device.generate_recovery_codes()
            request.session["_2fa_recovery_codes"] = codes
            messages.success(request, "New recovery codes generated.")
        return redirect("settings:two_factor")


class TwoFactorAwareLoginView(DjangoLoginView):
    """LoginView that redirects confirmed-2FA users to the challenge step."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["allow_registration"] = getattr(
            settings, "ALLOW_PUBLIC_REGISTRATION", False)
        return ctx

    def form_valid(self, form):
        user = form.get_user()
        device = getattr(user, "two_factor", None)
        if device and device.confirmed:
            self.request.session["pre_2fa_user_id"] = user.pk
            self.request.session["pre_2fa_next"] = self.get_success_url()
            self.request.session["pre_2fa_started_at"] = timezone.now().isoformat()
            self.request.session["pre_2fa_attempts"] = 0
            # Carry forward whichever backend authenticated the user. Falls back to
            # the first configured backend (ModelBackend by default).
            backend = getattr(user, "backend", None) or settings.AUTHENTICATION_BACKENDS[0]
            self.request.session["pre_2fa_backend"] = backend
            return HttpResponseRedirect(reverse("two_factor_challenge"))
        return super().form_valid(form)


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("code"), name="dispatch")
class TwoFactorChallengeView(View):
    MAX_ATTEMPTS = 5
    EXPIRY_SECONDS = 600  # 10 minutes

    def _abandon_and_redirect(self, request):
        for key in ("pre_2fa_user_id", "pre_2fa_next", "pre_2fa_attempts",
                    "pre_2fa_started_at", "pre_2fa_backend"):
            request.session.pop(key, None)
        return redirect("login")

    def _session_valid(self, request):
        if "pre_2fa_user_id" not in request.session:
            return False
        started = request.session.get("pre_2fa_started_at")
        if not started:
            return False
        try:
            age = (timezone.now() - datetime.fromisoformat(started)).total_seconds()
        except (ValueError, TypeError):
            return False
        if age > self.EXPIRY_SECONDS:
            return False
        if request.session.get("pre_2fa_attempts", 0) >= self.MAX_ATTEMPTS:
            return False
        return True

    def get(self, request):
        if not self._session_valid(request):
            return self._abandon_and_redirect(request)
        return render(request, "registration/two_factor_challenge.html", {
            "form": TwoFactorChallengeForm(),
        })

    def post(self, request):
        if not self._session_valid(request):
            return self._abandon_and_redirect(request)

        User_ = get_user_model()
        uid = request.session["pre_2fa_user_id"]
        user = User_.objects.filter(pk=uid).first()
        if user is None or not user.is_active:
            return self._abandon_and_redirect(request)

        form = TwoFactorChallengeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"].strip()
            device = user.two_factor
            # Try both paths — recovery-code alphabet excludes digits 0/1 so collision
            # with a 6-digit TOTP is impossible, but being explicit is clearer.
            ok = device.verify_totp(code) or device.verify_recovery_code(code)
            if ok:
                next_url = request.session.pop("pre_2fa_next", None) or settings.LOGIN_REDIRECT_URL
                backend = request.session.pop("pre_2fa_backend", None) \
                          or settings.AUTHENTICATION_BACKENDS[0]
                for key in ("pre_2fa_user_id", "pre_2fa_attempts", "pre_2fa_started_at"):
                    request.session.pop(key, None)
                user.backend = backend
                auth_login(request, user)
                return HttpResponseRedirect(next_url)
            request.session["pre_2fa_attempts"] = request.session.get("pre_2fa_attempts", 0) + 1
            remaining = self.MAX_ATTEMPTS - request.session["pre_2fa_attempts"]
            if remaining <= 0:
                return self._abandon_and_redirect(request)
            form.add_error("code",
                           f"Invalid code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")

        return render(request, "registration/two_factor_challenge.html", {"form": form})


class EmailVerifyPromptView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.email_verified_at is not None:
            return redirect("/")
        return render(request, "registration/email_verify_prompt.html")


class EmailVerifyResendView(LoginRequiredMixin, View):
    COOLDOWN_SECONDS = 60

    def post(self, request):
        import datetime
        stamp = request.session.get("verify_email_sent_at")
        now = timezone.now()
        if stamp:
            try:
                last = datetime.datetime.fromisoformat(stamp)
                if (now - last).total_seconds() < self.COOLDOWN_SECONDS:
                    messages.info(request, "Please wait a moment before requesting another link.")
                    return redirect("email_verify_prompt")
            except (ValueError, TypeError):
                pass
        send_verify_email(request.user, request)
        request.session["verify_email_sent_at"] = now.isoformat()
        messages.success(request, "A new verification link was sent.")
        return redirect("email_verify_prompt")


class EmailVerifyConfirmView(View):
    def get(self, request, uidb64, token):
        User_ = get_user_model()
        try:
            uid = int(force_str(urlsafe_base64_decode(uidb64)))
        except (ValueError, TypeError):
            return render(request, "registration/email_verify_invalid.html")
        user = User_.objects.filter(pk=uid).first()
        if user is None:
            return render(request, "registration/email_verify_invalid.html")
        # Idempotent: already verified → success redirect
        if user.email_verified_at is not None:
            messages.success(request, "Your email is already verified.")
            return redirect("/")
        if not default_token_generator.check_token(user, token):
            return render(request, "registration/email_verify_invalid.html")
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
        if not request.user.is_authenticated:
            user.backend = settings.AUTHENTICATION_BACKENDS[0]
            auth_login(request, user)
        messages.success(request, "Email verified — you're all set.")
        return redirect("/")


@method_decorator(never_cache, name="dispatch")
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class ConfirmPasswordView(LoginRequiredMixin, View):
    template_name = "registration/confirm_password.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": PasswordConfirmForm(user=request.user),
            "next": request.GET.get("next", "/"),
        })

    def post(self, request):
        form = PasswordConfirmForm(request.POST, user=request.user)
        next_url = request.POST.get("next") or "/"
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = "/"
        if form.is_valid():
            request.session["password_confirmed_at"] = timezone.now().isoformat()
            return HttpResponseRedirect(next_url)
        return render(request, self.template_name, {"form": form, "next": next_url})


class LockScreenView(View):
    """Session-lock screen.

    GET (when not yet locked): set session["locked"] and render the lock template.
    GET (when already locked): just render the lock template.
    POST: re-authenticate the current user with their password; on success
    clear the lock flag and redirect to the dashboard.
    """

    template_name = "accounts/lock.html"

    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("login")
        request.session["locked"] = True
        request.session.modified = True
        return render(request, self.template_name)

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("login")
        from django.contrib.auth import authenticate
        password = request.POST.get("password", "")
        user = authenticate(username=request.user.username, password=password)
        if user is not None:
            request.session.pop("locked", None)
            request.session.modified = True
            return redirect("dashboard")
        return render(request, self.template_name, {"error": "Incorrect password."})
