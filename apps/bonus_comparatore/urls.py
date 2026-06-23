from django.urls import path

from . import views

app_name = "bonus_comparatore"

urlpatterns = [
    path("", views.BonusHomeView.as_view(), name="home"),
    path("api/livescores/", views.LiveScoresApiView.as_view(), name="livescores_api"),
    path("api/news/", views.NewsApiView.as_view(), name="news_api"),
    path("api/match/detail/", views.MatchDetailApiView.as_view(), name="match_detail_api"),
    path("go/<slug:slug>/", views.BookmakerGoView.as_view(), name="go"),
    path("<slug:slug>/", views.BookmakerDetailView.as_view(), name="detail"),
]
