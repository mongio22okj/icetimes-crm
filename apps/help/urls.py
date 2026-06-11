from django.urls import path

from . import views

app_name = "help_center"

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.search, name="search"),
    path("c/<slug:slug>/", views.category_detail, name="category"),
    path("a/<slug:slug>/", views.article_detail, name="article"),
]
