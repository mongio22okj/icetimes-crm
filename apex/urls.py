"""URL configuration for apex project."""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.views import (
    ConfirmPasswordView,
    EmailVerifyConfirmView,
    EmailVerifyPromptView,
    EmailVerifyResendView,
    LockScreenView,
    TwoFactorAwareLoginView,
    TwoFactorChallengeView,
)
from apps.api.api import api as ninja_api
from apps.leads.tracking import create_lead, tracking_redirect
from apps.leads.views import BrokerLandingSubmitView, BrokerLandingView
from apps.core.health import health as health_view
from apps.core.pwa import manifest as pwa_manifest
from apps.core.pwa import offline as pwa_offline
from apps.core.pwa import service_worker as pwa_sw
from apps.core.search import global_search
from apps.organizations.views import InvitationAcceptView


def robots_txt(request):
    lines = "User-agent: *\nDisallow: /\n"
    return HttpResponse(lines, content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("__health/", health_view, name="health"),
    path("manifest.webmanifest", pwa_manifest, name="pwa_manifest"),
    path("sw.js", pwa_sw, name="pwa_sw"),
    path("offline/", pwa_offline, name="pwa_offline"),
    path("robots.txt", robots_txt, name="robots"),
    path("comparatore/", TemplateView.as_view(template_name="comparatore.html"),
         name="comparatore"),
    path("bonus/", include("apps.bonus_comparatore.urls")),
    path("i18n/", include("django.conf.urls.i18n")),
    path("search/", global_search, name="search"),
    path("api/v1/", ninja_api.urls),
    path("api/track/", include("apps.leads.tracking_urls")),
    # Alias compatibile con landing che usano /api/create-lead (stesso handler).
    path("api/create-lead", create_lead, name="create_lead_alias_noslash"),
    path("api/create-lead/", create_lead, name="create_lead_alias"),
    path("accounts/login/",
         TwoFactorAwareLoginView.as_view(template_name="registration/login.html"),
         name="login"),
    path("accounts/two-factor/", TwoFactorChallengeView.as_view(), name="two_factor_challenge"),
    path("email/verify/", EmailVerifyPromptView.as_view(), name="email_verify_prompt"),
    path("email/verify/resend/", EmailVerifyResendView.as_view(), name="email_verify_resend"),
    path("email/verify/<uidb64>/<token>/", EmailVerifyConfirmView.as_view(), name="email_verify_confirm"),
    path("password/confirm/", ConfirmPasswordView.as_view(), name="confirm_password"),
    path("lock/", LockScreenView.as_view(), name="lock"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password-reset/", auth_views.PasswordResetView.as_view(
        template_name="registration/password_reset_form.html",
        email_template_name="registration/password_reset_email.txt",
        html_email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
    ), name="password_reset"),
    path("accounts/password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
    ), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password_reset_complete"),
    path("accounts/", include("apps.accounts.urls")),
    path("users/", include("apps.accounts.user_urls")),
    path("settings/", include("apps.accounts.settings_urls")),
    path("products/", include("apps.products.urls")),
    path("leads/", include("apps.leads.urls")),
    # Area visualizzatori (sola lettura lead) — esente dal gate del sito.
    path("viewer/", include("apps.leads.viewer_urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("orgs/", include("apps.organizations.urls")),
    path("invitations/<str:token>/", InvitationAcceptView.as_view(), name="invitation_accept"),
    # Link corti di tracciamento — /t/<code>/ → redirect tracciato.
    path("t/<str:code>/", tracking_redirect, name="tracking_redirect"),
    # Public broker landing pages.
    path("b/<slug:slug>/", BrokerLandingView.as_view(), name="broker_landing"),
    path("b/<slug:slug>/submit/", BrokerLandingSubmitView.as_view(), name="broker_landing_submit"),
    path("realtime/", include("apps.realtime.urls")),
    path("pages/", include("apps.core.urls")),
    path("", include("apps.dashboard.urls")),
]

if getattr(settings, "METRICS_ENABLED", False):
    urlpatterns += [
        path("__metrics/", include("django_prometheus.urls")),
    ]

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
