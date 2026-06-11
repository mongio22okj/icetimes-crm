from django.urls import path
from django.views.generic import RedirectView

from .settings_views import (
    AccountDeletionView,
    APITokensView,
    AuditLogView,
    DataExportView,
    DeleteWebhookView,
    RevokeAPITokenView,
    RevokeOtherSessionsView,
    RevokeSessionView,
    SessionsView,
    WebhooksView,
)
from .views import (
    AppearanceView,
    PasswordChangeView,
    ProfileView,
    TwoFactorDisableView,
    TwoFactorEnableView,
    TwoFactorRegenerateView,
    TwoFactorSetupView,
    TwoFactorView,
)

app_name = "settings"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="settings:profile", permanent=False)),
    # Existing panes
    path("profile/", ProfileView.as_view(), name="profile"),
    path("password/", PasswordChangeView.as_view(), name="password"),
    path("appearance/", AppearanceView.as_view(), name="appearance"),
    path("two-factor/", TwoFactorView.as_view(), name="two_factor"),
    path("two-factor/enable/", TwoFactorEnableView.as_view(), name="two_factor_enable"),
    path("two-factor/setup/", TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("two-factor/disable/", TwoFactorDisableView.as_view(), name="two_factor_disable"),
    path("two-factor/regenerate/", TwoFactorRegenerateView.as_view(), name="two_factor_regenerate"),
    # Phase 17 — Sessions
    path("sessions/", SessionsView.as_view(), name="sessions"),
    path("sessions/<str:session_key>/revoke/",
         RevokeSessionView.as_view(), name="revoke_session"),
    path("sessions/revoke-others/",
         RevokeOtherSessionsView.as_view(), name="revoke_other_sessions"),
    # Phase 17 — API tokens
    path("api-tokens/", APITokensView.as_view(), name="api_tokens"),
    path("api-tokens/<int:pk>/revoke/",
         RevokeAPITokenView.as_view(), name="revoke_api_token"),
    # Phase 17 — Webhooks
    path("webhooks/", WebhooksView.as_view(), name="webhooks"),
    path("webhooks/<int:pk>/delete/",
         DeleteWebhookView.as_view(), name="delete_webhook"),
    # Phase 17 — Audit log
    path("audit-log/", AuditLogView.as_view(), name="audit_log"),
    # Phase 17 — Data export
    path("data-export/", DataExportView.as_view(), name="data_export"),
    # Phase 17 — Account deletion
    path("account-deletion/", AccountDeletionView.as_view(), name="account_deletion"),
]
