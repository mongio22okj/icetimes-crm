from django.urls import path

from apps.events import views

app_name = "events"

urlpatterns = [
    path("", views.CalendarView.as_view(), name="calendar"),
    path("events/", views.EventJsonView.as_view(), name="event_json"),
    path("events/new/", views.EventCreateView.as_view(), name="create"),
    path("events/<int:pk>/edit/", views.EventUpdateView.as_view(), name="edit"),
    path("events/<int:pk>/delete/", views.EventDeleteView.as_view(), name="delete"),
]
