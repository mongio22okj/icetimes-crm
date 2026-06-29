from django.urls import path

from .views import (
    BrokerListView,
    GuideView,
    IrevBrokerCreateView,
    IrevBrokerDeleteView,
    IrevBrokerUpdateView,
    LeadListView,
    LeadPushView,
    LeadSyncSelectedView,
    SpmMonsterBrokerCreateView,
    SpmMonsterBrokerDeleteView,
    SpmMonsterBrokerSyncView,
    SpmMonsterBrokerUpdateView,
    SyncAllView,
    GalassiaBrokerCreateView,
    GalassiaBrokerDeleteView,
    GalassiaBrokerSyncView,
    GalassiaBrokerUpdateView,
    TYourAdsBrokerCreateView,
    TYourAdsBrokerDeleteView,
    TYourAdsBrokerUpdateView,
    TrackboxBrokerCreateView,
    TrackboxBrokerDeleteView,
    TrackboxBrokerSyncView,
    TrackboxBrokerUpdateView,
    TrackingCodeView,
)

app_name = "tracking"

urlpatterns = [
    path("", LeadListView.as_view(), name="lead_list"),
    path("leads/<int:pk>/push/", LeadPushView.as_view(), name="lead_push"),
    path("leads/sync-selected/", LeadSyncSelectedView.as_view(), name="lead_sync_selected"),
    path("sync-all/", SyncAllView.as_view(), name="sync_all"),
    path("guida/", GuideView.as_view(), name="guide"),
    # Broker API — lista unificata
    path("brokers/", BrokerListView.as_view(), name="broker_list"),
    # TrackBox
    path("brokers/trackbox/new/", TrackboxBrokerCreateView.as_view(), name="broker_create"),
    path("brokers/trackbox/<int:pk>/edit/", TrackboxBrokerUpdateView.as_view(), name="broker_edit"),
    path("brokers/trackbox/<int:pk>/delete/", TrackboxBrokerDeleteView.as_view(), name="broker_delete"),
    path("brokers/trackbox/<int:pk>/sync/", TrackboxBrokerSyncView.as_view(), name="broker_sync"),
    # IREV
    path("brokers/irev/new/", IrevBrokerCreateView.as_view(), name="irev_create"),
    path("brokers/irev/<int:pk>/edit/", IrevBrokerUpdateView.as_view(), name="irev_edit"),
    path("brokers/irev/<int:pk>/delete/", IrevBrokerDeleteView.as_view(), name="irev_delete"),
    # SPM Monster
    path("brokers/spm/new/", SpmMonsterBrokerCreateView.as_view(), name="spm_create"),
    path("brokers/spm/<int:pk>/edit/", SpmMonsterBrokerUpdateView.as_view(), name="spm_edit"),
    path("brokers/spm/<int:pk>/delete/", SpmMonsterBrokerDeleteView.as_view(), name="spm_delete"),
    path("brokers/spm/<int:pk>/sync/", SpmMonsterBrokerSyncView.as_view(), name="spm_sync"),

    path("brokers/tyourads/new/", TYourAdsBrokerCreateView.as_view(), name="tyourads_create"),
    path("brokers/tyourads/<int:pk>/edit/", TYourAdsBrokerUpdateView.as_view(), name="tyourads_edit"),
    path("brokers/tyourads/<int:pk>/delete/", TYourAdsBrokerDeleteView.as_view(), name="tyourads_delete"),

    path("brokers/galassia/new/", GalassiaBrokerCreateView.as_view(), name="galassia_create"),
    path("brokers/galassia/<int:pk>/edit/", GalassiaBrokerUpdateView.as_view(), name="galassia_edit"),
    path("brokers/galassia/<int:pk>/delete/", GalassiaBrokerDeleteView.as_view(), name="galassia_delete"),
    path("brokers/galassia/<int:pk>/sync/", GalassiaBrokerSyncView.as_view(), name="galassia_sync"),
    # Codice tracciamento per landing esterna (snippet form)
    path("brokers/<str:kind>/<int:pk>/code/", TrackingCodeView.as_view(), name="broker_code"),
]
