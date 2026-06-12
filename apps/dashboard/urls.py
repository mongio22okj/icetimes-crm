from django.urls import path

from .views import LeadBrokerDashboardView

# Real CRM dashboard for IceTimes: KPI cards + charts + activity feed
# powered by Lead / Sale data. The URL name "dashboard" is reused (logo
# link, breadcrumb root, post-login + unlock redirects all reverse it).
urlpatterns = [
    path("", LeadBrokerDashboardView.as_view(), name="dashboard"),
]
