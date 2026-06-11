from django.urls import path

from apps.profiles import views

app_name = "profiles"

urlpatterns = [
    path("", views.PeopleListView.as_view(), name="list"),
    path("<str:username>/", views.ProfileOverviewView.as_view(), name="overview"),
    path("<str:username>/projects/", views.ProfileProjectsView.as_view(), name="projects"),
    path("<str:username>/activity/", views.ProfileActivityView.as_view(), name="activity"),
    path("<str:username>/connections/", views.ProfileConnectionsView.as_view(), name="connections"),
]
