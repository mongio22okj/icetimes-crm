from django.urls import path

from apps.components import views

app_name = "components"

urlpatterns = [
    path("", views.ComponentIndexView.as_view(), name="index"),
    path("<slug:slug>/", views.ComponentDetailView.as_view(), name="detail"),
]
