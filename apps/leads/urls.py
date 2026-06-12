from django.urls import path

from .views import (
    LeadListView,
    LeadSendView,
    LeadSyncView,
    SourceCreateView,
    SourceDeleteView,
    SourceListView,
    SourceUpdateView,
    postback,
)

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("send/", LeadSendView.as_view(), name="send"),
    path("sync/", LeadSyncView.as_view(), name="sync"),
    path("postback/", postback, name="postback"),
    path("sources/", SourceListView.as_view(), name="sources"),
    path("sources/new/", SourceCreateView.as_view(), name="source_create"),
    path("sources/<int:pk>/", SourceUpdateView.as_view(), name="source_edit"),
    path("sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="source_delete"),
]
