from django.urls import path

from .views import (
    CustomerArchiveView,
    CustomerCreateView,
    CustomerDetailView,
    CustomerListView,
    CustomerUpdateView,
)

app_name = "customers"

urlpatterns = [
    path("", CustomerListView.as_view(), name="list"),
    path("new/", CustomerCreateView.as_view(), name="create"),
    path("<int:pk>/", CustomerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", CustomerUpdateView.as_view(), name="edit"),
    path("<int:pk>/archive/", CustomerArchiveView.as_view(), name="archive"),
]
