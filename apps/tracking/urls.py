from django.urls import path

from .views import (
    LeadListView,
    LeadPushView,
    TrackboxBrokerCreateView,
    TrackboxBrokerDeleteView,
    TrackboxBrokerListView,
    TrackboxBrokerSyncView,
    TrackboxBrokerUpdateView,
)

app_name = "tracking"

urlpatterns = [
    path("", LeadListView.as_view(), name="lead_list"),
    path("leads/<int:pk>/push/", LeadPushView.as_view(), name="lead_push"),
    path("brokers/", TrackboxBrokerListView.as_view(), name="broker_list"),
    path("brokers/new/", TrackboxBrokerCreateView.as_view(), name="broker_create"),
    path("brokers/<int:pk>/edit/", TrackboxBrokerUpdateView.as_view(), name="broker_edit"),
    path("brokers/<int:pk>/delete/", TrackboxBrokerDeleteView.as_view(), name="broker_delete"),
    path("brokers/<int:pk>/sync/", TrackboxBrokerSyncView.as_view(), name="broker_sync"),
]
