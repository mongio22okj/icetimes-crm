from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.post_list, name="list"),
    path("t/<slug:slug>/", views.topic_detail, name="topic"),
    path("<slug:slug>/", views.post_detail, name="detail"),
]
