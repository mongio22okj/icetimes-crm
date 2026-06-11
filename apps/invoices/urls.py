from django.urls import path

from apps.invoices import views

app_name = "invoices"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="list"),
    path("new/", views.InvoiceCreateView.as_view(), name="create"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.InvoiceUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.InvoiceDeleteView.as_view(), name="delete"),
    path("<int:pk>/send/", views.InvoiceSendView.as_view(), name="send"),
    path("<int:pk>/pay/", views.InvoicePayView.as_view(), name="pay"),
    path("<int:pk>/void/", views.InvoiceVoidView.as_view(), name="void"),
    path("<int:pk>/pdf/", views.InvoicePdfView.as_view(), name="pdf"),
    path("items/add-row/", views.InvoiceItemAddRowView.as_view(), name="add_row"),
    path("public/<uuid:token>/", views.PublicInvoiceView.as_view(), name="public"),
    path("public/<uuid:token>/pdf/", views.PublicInvoicePdfView.as_view(), name="public_pdf"),
]
