from django.urls import path

from .views import (
    IntegrationsView,
    LeadListView,
    LeadSyncView,
    SourceCreateView,
    SourceDeleteView,
    SourceUpdateView,
    postback,
)

app_name = "leads"

urlpatterns = [
    path("", LeadListView.as_view(), name="list"),
    path("integrations/", IntegrationsView.as_view(), name="integrations"),
    path("sync/", LeadSyncView.as_view(), name="sync"),
    path("postback/", postback, name="postback"),
    # LeadSource CRUD — reachable from Django admin or directly via URL.
    path("sources/new/", SourceCreateView.as_view(), name="source_create"),
    path("sources/<int:pk>/", SourceUpdateView.as_view(), name="source_edit"),
    path("sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="source_delete"),
]
