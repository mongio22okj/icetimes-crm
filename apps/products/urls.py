from django.urls import path

from .views import (
    ProductCreateView,
    ProductDetailView,
    ProductListView,
    ProductUpdateView,
    SaleListView,
    SaleUpdateStatusView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("new/", ProductCreateView.as_view(), name="create"),
    # Sales — placed BEFORE int:pk routes so /sales/ does not match <int:pk>.
    path("sales/", SaleListView.as_view(), name="sale_list"),
    path("sales/<int:pk>/status/", SaleUpdateStatusView.as_view(), name="sale_update_status"),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="edit"),
]
