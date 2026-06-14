from django.urls import path
from .tracking import create_lead, track_click, track_visit

urlpatterns = [
    path("visit/", track_visit, name="track_visit"),
    path("click/", track_click, name="track_click"),
    path("lead/", create_lead, name="track_lead"),
]
