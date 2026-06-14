from django.urls import path

from .views import (
    AnalyticsDashboardView,
    ChartsShowcaseView,
    CrmDashboardView,
    EcommerceDashboardView,
    LeadBrokerDashboardView,
    SaasDashboardView,
    revenue_chart_data,
)

urlpatterns = [
    path("", LeadBrokerDashboardView.as_view(), name="dashboard"),
    path("dashboards/analytics/", AnalyticsDashboardView.as_view(),
         name="dashboard_analytics"),
    path("dashboards/crm/", CrmDashboardView.as_view(), name="dashboard_crm"),
    path("dashboards/ecommerce/", EcommerceDashboardView.as_view(),
         name="dashboard_ecommerce"),
    path("dashboards/saas/", SaasDashboardView.as_view(), name="dashboard_saas"),
    path("charts/", ChartsShowcaseView.as_view(), name="charts_showcase"),
    path("charts/revenue/", revenue_chart_data, name="revenue_chart_data"),
]
