from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("plans/", views.plans, name="plans"),
    path("plans/change/", views.ChangePlanView.as_view(), name="change_plan"),
    path("payment-methods/", views.PaymentMethodsView.as_view(), name="payment_methods"),
    path("payment-methods/<int:pk>/default/",
         views.SetDefaultPaymentMethodView.as_view(), name="set_default_pm"),
    path("payment-methods/<int:pk>/delete/",
         views.DeletePaymentMethodView.as_view(), name="delete_pm"),
    path("cancel/", views.CancelView.as_view(), name="cancel"),
]
