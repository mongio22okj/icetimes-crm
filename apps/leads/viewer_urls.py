from django.urls import path

from .viewer import (
    ViewerDashboardView,
    ViewerDataView,
    ViewerLoginView,
    ViewerLogoutView,
)

app_name = "viewer"

urlpatterns = [
    path("", ViewerDashboardView.as_view(), name="dashboard"),
    path("login/", ViewerLoginView.as_view(), name="login"),
    path("logout/", ViewerLogoutView.as_view(), name="logout"),
    path("data/", ViewerDataView.as_view(), name="data"),
]
