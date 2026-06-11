from django.urls import path

from apps.notifications import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("preferences/", views.PreferencesView.as_view(), name="preferences"),
    path("bell/", views.BellView.as_view(), name="bell"),
    path("<int:pk>/read/", views.MarkReadView.as_view(), name="mark_read"),
    path("<int:pk>/archive/", views.ArchiveView.as_view(), name="archive"),
    path("read-all/", views.MarkAllReadView.as_view(), name="mark_all"),
    path("push/subscribe/", views.PushSubscribeView.as_view(), name="push_subscribe"),
    path("push/unsubscribe/", views.PushUnsubscribeView.as_view(), name="push_unsubscribe"),
]
