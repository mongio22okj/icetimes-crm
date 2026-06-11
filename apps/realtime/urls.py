from django.urls import path

from apps.realtime import views

app_name = "realtime"

urlpatterns = [
    path("", views.RealtimeDemoView.as_view(), name="demo"),
    path("fire/", views.FireTestNotificationView.as_view(),
         name="fire_test"),
]
