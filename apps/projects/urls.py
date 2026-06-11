from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.ProjectOverviewView.as_view(), name="overview"),
    path("<slug:slug>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<slug:slug>/archive/", views.ProjectArchiveView.as_view(), name="archive"),
    path("<slug:slug>/tasks/", views.ProjectTasksView.as_view(), name="tasks"),
    path("<slug:slug>/tasks/create/", views.ProjectTaskCreateView.as_view(), name="task_create"),
    path("<slug:slug>/tasks/<int:pk>/toggle/",
         views.ProjectTaskToggleStatusView.as_view(), name="task_toggle"),
    path("<slug:slug>/tasks/<int:pk>/delete/",
         views.ProjectTaskDeleteView.as_view(), name="task_delete"),
    path("<slug:slug>/team/", views.ProjectTeamView.as_view(), name="team"),
    path("<slug:slug>/activity/", views.ProjectActivityView.as_view(), name="activity"),
    path("<slug:slug>/milestones/create/",
         views.MilestoneCreateView.as_view(), name="milestone_create"),
    path("<slug:slug>/milestones/<int:pk>/toggle/",
         views.MilestoneToggleView.as_view(), name="milestone_toggle"),
]
