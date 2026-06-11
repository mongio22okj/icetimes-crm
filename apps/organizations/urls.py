from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("", views.OrgListView.as_view(), name="list"),
    path("switch/<slug:slug>/", views.OrgSwitchView.as_view(), name="switch"),
    path("<slug:slug>/settings/", views.OrgSettingsView.as_view(), name="settings"),
    path("<slug:slug>/members/", views.MembersView.as_view(), name="members"),
    path("<slug:slug>/members/invite/", views.InviteView.as_view(), name="invite"),
    path("<slug:slug>/members/<int:pk>/role/",
         views.ChangeRoleView.as_view(), name="change_role"),
    path("<slug:slug>/members/<int:pk>/remove/",
         views.RemoveMemberView.as_view(), name="remove_member"),
    path("<slug:slug>/invitations/<int:pk>/cancel/",
         views.CancelInvitationView.as_view(), name="cancel_invitation"),
]
