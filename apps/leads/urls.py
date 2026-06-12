from django.urls import path

from .views import LeadListView, LeadSendView, LeadSyncIrevView, postback

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("send/", LeadSendView.as_view(), name="send"),
    path("sync-irev/", LeadSyncIrevView.as_view(), name="sync_irev"),
    path("postback/", postback, name="postback"),
]
