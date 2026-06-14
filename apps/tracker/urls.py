from django.urls import path
from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("report/<int:campaign_id>/", views.report, name="report"),
    # API
    path("api/brokers/", views.api_brokers, name="api_brokers"),
    path("api/brokers/<int:pk>/delete/", views.api_broker_delete, name="api_broker_delete"),
    path("api/campaigns/", views.api_campaigns, name="api_campaigns"),
    path("api/campaigns/<int:pk>/delete/", views.api_campaign_delete, name="api_campaign_delete"),
]
