from django.urls import path

from apps.wizard import views

app_name = "wizard"

urlpatterns = [
    path("", views.StartView.as_view(), name="start"),
    path("step/1/", views.Step1View.as_view(), name="step1"),
    path("step/2/", views.Step2View.as_view(), name="step2"),
    path("step/3/", views.Step3View.as_view(), name="step3"),
    path("review/", views.ReviewView.as_view(), name="review"),
    path("done/", views.DoneView.as_view(), name="done"),
]
