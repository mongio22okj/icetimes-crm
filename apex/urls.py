"""
URL configuration for apex project.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path

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
from apps.core.health import health as health_view
from apps.core.pwa import manifest as pwa_manifest
from apps.core.pwa import offline as pwa_offline
from apps.core.pwa import service_worker as pwa_sw
from apps.core.search import global_search
from apps.marketing.sitemaps import MarketingSitemap
from apps.organizations.views import InvitationAcceptView
from apps.products.views import ProductLandingView, ProductSubmitView


def robots_txt(request):
    """robots.txt — allow public marketing pages, disallow app + admin."""
    body = (
        "User-agent: *\n"
        "Allow: /landing/\n"
        "Allow: /blog/\n"
        "Allow: /help/\n"
        "Disallow: /admin/\n"
        "Disallow: /api/\n"
        "Disallow: /accounts/\n"
        "Disallow: /settings/\n"
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml\n"
    )
    return HttpResponse(body, content_type="text/plain")


SITEMAPS = {"marketing": MarketingSitemap}


urlpatterns = [
    path("admin/", admin.site.urls),
    # Health check for uptime monitors / load balancers — anonymous, no-cache.
    path("__health/", health_view, name="health"),
    # PWA — manifest + service worker + offline fallback.
    # SW lives at root so its scope can claim the entire origin.
    path("manifest.webmanifest", pwa_manifest, name="pwa_manifest"),
    path("sw.js",                pwa_sw,       name="pwa_sw"),
    path("offline/",             pwa_offline,  name="pwa_offline"),
    # Public hosted docs — no auth, mirrors the Next.js Apex docs structure.
    path("docs/", include("apps.docs.urls")),
    # Ninja-served API (Swagger UI at /api/v1/docs, OpenAPI at /api/v1/openapi.json).
    path("api/v1/", ninja_api.urls),
    # Phase 18 — SEO surface
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("search/", global_search, name="search"),
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
    # Public product landing — short URL, ad-friendly.
    path("p/<slug:slug>/", ProductLandingView.as_view(), name="product_landing"),
    path("p/<slug:slug>/submit/", ProductSubmitView.as_view(), name="product_submit"),
    path("customers/", include("apps.customers.urls")),
    path("calendar/", include("apps.events.urls")),
    path("chat/", include("apps.chat.urls")),
    path("files/", include("apps.files.urls")),
    path("invoices/", include("apps.invoices.urls")),
    path("kanban/", include("apps.kanban.urls")),
    path("leads/", include("apps.leads.urls")),
    path("landing/", include("apps.marketing.urls")),
    path("mail/", include("apps.mail.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("orders/", include("apps.orders.urls")),
    path("projects/", include("apps.projects.urls")),
    path("people/", include("apps.profiles.urls")),
    path("activity/", include("apps.activity.urls")),
    # Phase 16 — Organizations
    path("orgs/", include("apps.organizations.urls")),
    path("invitations/<str:token>/", InvitationAcceptView.as_view(),
         name="invitation_accept"),
    # Phase 14 — Realtime demo + test-trigger
    path("realtime/", include("apps.realtime.urls")),
    path("pages/", include("apps.core.urls")),
    path("billing/", include("apps.billing.urls")),
    path("help/", include("apps.help.urls")),
    path("blog/", include("apps.blog.urls")),
    path("wizard/", include("apps.wizard.urls")),
    path("components/", include("apps.components.urls")),
    path("", include("apps.dashboard.urls")),  # root URL last
]

# Prometheus metrics — only mounted when METRICS_ENABLED env var is set.
# Endpoint is /__metrics/ (double underscore = "internal, not for humans"
# — same convention as /__health/). Returns Prometheus text-exposition
# format; scrape with Prometheus / Grafana Cloud / Datadog Agent.
if getattr(settings, "METRICS_ENABLED", False):
    urlpatterns += [
        path("__metrics/", include("django_prometheus.urls")),
    ]


handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
