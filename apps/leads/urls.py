from django.urls import path

from .views import (
    AutoMessageCreateView,
    AutoMessageDeleteView,
    AutoMessageListView,
    AutoMessageUpdateView,
    BrokersDashboardView,
    CampaignCreateView,
    CampaignDeleteView,
    CampaignListView,
    CampaignUpdateView,
    DispatchLogView,
    IntegrationsView,
    LeadDispatchTriggerView,
    LeadListView,
    LeadSyncView,
    NotificationCreateView,
    NotificationDeleteView,
    NotificationListView,
    NotificationTestView,
    NotificationUpdateView,
    PartnerCreateView,
    PartnerDeleteView,
    PartnerListView,
    PartnerUpdateView,
    ReportsView,
    SourceCreateView,
    SourceDeleteView,
    SourceUpdateView,
    postback,
)

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("brokers/", BrokersDashboardView.as_view(), name="brokers_dashboard"),
    path("campaigns/", CampaignListView.as_view(), name="campaign_list"),
    path("campaigns/new/", CampaignCreateView.as_view(), name="campaign_create"),
    path("campaigns/<int:pk>/", CampaignUpdateView.as_view(), name="campaign_edit"),
    path("campaigns/<int:pk>/delete/", CampaignDeleteView.as_view(), name="campaign_delete"),
    path("reports/", ReportsView.as_view(), name="reports"),
    # Notification webhooks (Slack / Discord / Telegram / generic).
    path("notifications/", NotificationListView.as_view(), name="notification_list"),
    path("notifications/new/", NotificationCreateView.as_view(), name="notification_create"),
    path("notifications/<int:pk>/", NotificationUpdateView.as_view(), name="notification_edit"),
    path("notifications/<int:pk>/delete/", NotificationDeleteView.as_view(), name="notification_delete"),
    path("notifications/<int:pk>/test/", NotificationTestView.as_view(), name="notification_test"),
    # Auto-email templates (speed-to-lead).
    path("auto-email/", AutoMessageListView.as_view(), name="auto_message_list"),
    path("auto-email/new/", AutoMessageCreateView.as_view(), name="auto_message_create"),
    path("auto-email/<int:pk>/", AutoMessageUpdateView.as_view(), name="auto_message_edit"),
    path("auto-email/<int:pk>/delete/", AutoMessageDeleteView.as_view(), name="auto_message_delete"),
    # Ping-tree dispatch log + manual trigger.
    path("dispatch/", DispatchLogView.as_view(), name="dispatch_log"),
    path("dispatch/<int:pk>/", LeadDispatchTriggerView.as_view(), name="lead_dispatch"),
    path("integrations/", IntegrationsView.as_view(), name="integrations"),
    path("sync/", LeadSyncView.as_view(), name="sync"),
    path("postback/", postback, name="postback"),
    # LeadSource CRUD — reachable from Django admin or directly via URL.
    path("sources/new/", SourceCreateView.as_view(), name="source_create"),
    path("sources/<int:pk>/", SourceUpdateView.as_view(), name="source_edit"),
    path("sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="source_delete"),
    # Partner API — lightweight partner/affiliate registry.
    path("partners/", PartnerListView.as_view(), name="partner_list"),
    path("partners/new/", PartnerCreateView.as_view(), name="partner_create"),
    path("partners/<int:pk>/", PartnerUpdateView.as_view(), name="partner_edit"),
    path("partners/<int:pk>/delete/", PartnerDeleteView.as_view(), name="partner_delete"),
]
