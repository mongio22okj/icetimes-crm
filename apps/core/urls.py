from django.urls import path

from apps.core import views

app_name = "pages"

urlpatterns = [
    path("coming-soon/", views.coming_soon, name="coming_soon"),
    path("coming-soon/subscribe/", views.coming_soon_subscribe,
         name="coming_soon_subscribe"),
    path("maintenance/", views.maintenance, name="maintenance"),
    path("503/", views.service_unavailable, name="service_unavailable"),
    path("forms/", views.forms_gallery, name="forms_gallery"),
    path("forms/_upload/", views.forms_gallery_upload, name="forms_gallery_upload"),
    path("widgets/", views.widgets_gallery, name="widgets_gallery"),
    path("datatable/", views.datatable_demo, name="datatable"),
    path("api-docs/", views.api_docs, name="api_docs"),
    path("maps/", views.maps_showcase, name="maps"),
]
