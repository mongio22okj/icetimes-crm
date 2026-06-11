from django.urls import path

from apps.mail import views

app_name = "mail"

urlpatterns = [
    path("", views.InboxView.as_view(), name="inbox"),
    path("inbox/", views.InboxView.as_view(), name="inbox_list"),
    path("sent/", views.SentView.as_view(), name="sent"),
    path("drafts/", views.DraftsView.as_view(), name="drafts"),
    path("starred/", views.StarredView.as_view(), name="starred"),
    path("trash/", views.TrashView.as_view(), name="trash"),
    path("compose/", views.ComposeView.as_view(), name="compose"),
    path("<int:pk>/", views.ThreadView.as_view(), name="thread"),
    path("<int:pk>/reply/", views.ReplyView.as_view(), name="reply"),
    path("<int:pk>/star/", views.StarToggleView.as_view(), name="star"),
    path("<int:pk>/trash/", views.TrashToggleView.as_view(), name="trash_toggle"),
    path("drafts/<int:pk>/edit/", views.ComposeView.as_view(), name="draft_edit"),
    path("drafts/<int:pk>/discard/", views.DraftDiscardView.as_view(), name="draft_discard"),
]
