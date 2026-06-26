from django.urls import path

from .views import (
    TrackboxBrokerCreateView,
    TrackboxBrokerDeleteView,
    TrackboxBrokerListView,
    TrackboxBrokerUpdateView,
)

app_name = "tracking"

urlpatterns = [
    path("brokers/", TrackboxBrokerListView.as_view(), name="broker_list"),
    path("brokers/new/", TrackboxBrokerCreateView.as_view(), name="broker_create"),
    path("brokers/<int:pk>/edit/", TrackboxBrokerUpdateView.as_view(), name="broker_edit"),
    path("brokers/<int:pk>/delete/", TrackboxBrokerDeleteView.as_view(), name="broker_delete"),
]
