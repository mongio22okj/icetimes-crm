from django.urls import path
from django.views.generic.base import RedirectView

from .views import (
    APIBrokerView,
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
    path("api-broker/", APIBrokerView.as_view(), name="api_broker"),
    path("integrations/", IntegrationsView.as_view(), name="integrations"),
    path("sync/", LeadSyncView.as_view(), name="sync"),
    path("postback/", postback, name="postback"),
    # Source CRUD (rendered as modal partials when called with ?modal=1).
    path("sources/new/", SourceCreateView.as_view(), name="source_create"),
    path("sources/<int:pk>/", SourceUpdateView.as_view(), name="source_edit"),
    path("sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="source_delete"),
    # Backward-compat URL aliases.
    path("send/", RedirectView.as_view(pattern_name="leads:api_broker", permanent=True)),
    path("sources/", RedirectView.as_view(pattern_name="leads:api_broker", permanent=True), name="sources"),
]
