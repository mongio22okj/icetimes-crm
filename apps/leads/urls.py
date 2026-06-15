from django.urls import path

from .views import (
    AutoMessageCreateView,
    AutoMessageDeleteView,
    AutoMessageListView,
    AutoMessageUpdateView,
    BrokerLandingListView,
    BrokersDashboardView,
    CampaignCreateView,
    CampaignDeleteView,
    CampaignListView,
    CampaignUpdateView,
    DispatchLogView,
    LeadDispatchTriggerView,
    LeadListView,
    LeadSourceCreateView,
    LeadSourceDeleteView,
    LeadSourceListView,
    LeadSourceUpdateView,
    LeadSyncView,
    NotificationCreateView,
    NotificationDeleteView,
    NotificationListView,
    NotificationTestView,
    NotificationUpdateView,
    ReportsView,
    postback,
)

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("brokers/", BrokersDashboardView.as_view(), name="brokers_dashboard"),
    # Lead source (broker API) CRUD.
    path("sources/", LeadSourceListView.as_view(), name="source_list"),
    path("sources/new/", LeadSourceCreateView.as_view(), name="source_create"),
    path("sources/<int:pk>/", LeadSourceUpdateView.as_view(), name="source_edit"),
    path("sources/<int:pk>/delete/", LeadSourceDeleteView.as_view(), name="source_delete"),
    # Broker landing pages management.
    path("landing/", BrokerLandingListView.as_view(), name="landing_list"),
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
    path("sync/", LeadSyncView.as_view(), name="sync"),
    path("postback/", postback, name="postback"),
]
