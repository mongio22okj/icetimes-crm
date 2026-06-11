from django.urls import path

from .views import LeadListView, LeadSendView

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("send/", LeadSendView.as_view(), name="send"),
]
