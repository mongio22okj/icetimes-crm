from django.urls import path

from apps.chat import views

app_name = "chat"

urlpatterns = [
    path("", views.ChatHomeView.as_view(), name="home"),
    path("new/", views.NewConversationView.as_view(), name="new"),
    path("<int:user_pk>/", views.ConversationView.as_view(), name="conversation"),
    path("<int:user_pk>/send/", views.SendMessageView.as_view(), name="send"),
    path("<int:user_pk>/stream/", views.StreamView.as_view(), name="stream"),
]
