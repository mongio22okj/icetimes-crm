from django.urls import path

from apps.kanban import views

app_name = "kanban"

urlpatterns = [
    path("", views.BoardView.as_view(), name="board"),
    path("cards/new/", views.CardCreateView.as_view(), name="create"),
    path("cards/<int:pk>/", views.CardDetailView.as_view(), name="detail"),
    path("cards/<int:pk>/edit/", views.CardUpdateView.as_view(), name="edit"),
    path("cards/<int:pk>/delete/", views.CardDeleteView.as_view(), name="delete"),
    path("cards/<int:pk>/move/", views.CardMoveView.as_view(), name="move"),
]
