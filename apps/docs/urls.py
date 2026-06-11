from django.urls import path

from apps.docs import views

app_name = "docs"

urlpatterns = [
    path("",                       views.IntroductionView.as_view(),    name="index"),
    path("installation/",          views.InstallationView.as_view(),    name="installation"),
    path("folder-structure/",      views.FolderStructureView.as_view(), name="folder_structure"),
    path("architecture/",          views.ArchitectureView.as_view(),    name="architecture"),
    path("customize/",             views.CustomizeView.as_view(),       name="customize"),
    path("theming/",               views.ThemingView.as_view(),         name="theming"),
    path("adding-pages/",          views.AddingPagesView.as_view(),     name="adding_pages"),
    path("components/",            views.ComponentsView.as_view(),      name="components"),
    path("charts/",                views.ChartsView.as_view(),          name="charts"),
    path("i18n/",                  views.I18nView.as_view(),            name="i18n"),
    path("deployment/",            views.DeploymentView.as_view(),      name="deployment"),
    path("demo-mode/",             views.DemoModeView.as_view(),        name="demo_mode"),
    path("backups/",               views.BackupsView.as_view(),         name="backups"),
    path("monitoring/",            views.MonitoringView.as_view(),      name="monitoring"),
    path("realtime/",              views.RealtimeView.as_view(),        name="realtime"),
    path("api/",                   views.ApiView.as_view(),             name="api"),
    path("organizations/",         views.OrganizationsView.as_view(),   name="organizations"),
    path("testing/",               views.TestingView.as_view(),         name="testing"),
    path("changelog/",             views.ChangelogView.as_view(),       name="changelog"),
    path("faq/",                   views.FaqView.as_view(),             name="faq"),
]
