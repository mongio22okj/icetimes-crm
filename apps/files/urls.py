from django.urls import path

from apps.files import views

app_name = "files"

urlpatterns = [
    path("", views.BrowserView.as_view(), name="root"),
    path("folder/<int:pk>/", views.BrowserView.as_view(), name="folder"),
    path("folder/new/", views.FolderCreateView.as_view(), name="folder_create"),
    path("folder/<int:pk>/rename/", views.FolderRenameView.as_view(), name="folder_rename"),
    path("folder/<int:pk>/delete/", views.FolderDeleteView.as_view(), name="folder_delete"),
    path("upload/", views.UploadView.as_view(), name="upload"),
    path("<int:pk>/download/", views.DownloadView.as_view(), name="download"),
    path("<int:pk>/rename/", views.FileRenameView.as_view(), name="file_rename"),
    path("<int:pk>/delete/", views.FileDeleteView.as_view(), name="file_delete"),
]
