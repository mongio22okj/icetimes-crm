from django.urls import path

from .views import (
    UserAccessToggleView,
    UserCreateView,
    UserDetailView,
    UserListView,
    UserUpdateView,
)

app_name = "users"

urlpatterns = [
    path("", UserListView.as_view(), name="list"),
    path("new/", UserCreateView.as_view(), name="create"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", UserUpdateView.as_view(), name="edit"),
    path("<int:pk>/access/", UserAccessToggleView.as_view(), name="access_toggle"),
]
