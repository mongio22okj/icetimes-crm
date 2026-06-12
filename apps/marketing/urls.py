from django.urls import path

from apps.marketing import views

app_name = "marketing"

urlpatterns = [
    path("", views.LandingsHubView.as_view(), name="hub"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("saas/", views.SaasView.as_view(), name="saas"),
    path("crm/", views.CrmView.as_view(), name="crm"),
    path("ecommerce/", views.EcommerceView.as_view(), name="ecommerce"),
    path("pricing/", views.PricingView.as_view(), name="pricing"),
    path("support/", views.SupportView.as_view(), name="support"),
    # Phase 18 — Marketing polish
    path("changelog/", views.ChangelogView.as_view(), name="changelog"),
    path("roadmap/", views.RoadmapView.as_view(), name="roadmap"),
    path("compare/", views.CompareView.as_view(), name="compare"),
    path("showcase/", views.ShowcaseView.as_view(), name="showcase"),
    # Lead-capture landings (public, no auth — submit handled server-side).
    path("newsletter/", views.NewsletterLandingView.as_view(), name="landing_newsletter"),
    path("trading/", views.TradingLandingView.as_view(), name="landing_trading"),
    path("submit/", views.LandingSubmitView.as_view(), name="landing_submit"),
]
