import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import Milestone, Project, ProjectTask
from apps.projects.tests.factories import (
    MilestoneFactory,
    ProjectFactory,
    ProjectTaskFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_user():
    return UserFactory(is_staff=True)


# ── Auth gates ─────────────────────────────────────────────────────────

def test_list_redirects_anonymous(client):
    r = client.get(reverse("projects:list"))
    assert r.status_code == 302


def test_list_forbidden_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("projects:list"))
    assert r.status_code == 403


# ── List + filter ──────────────────────────────────────────────────────

def test_list_renders_projects(client, staff_user):
    client.force_login(staff_user)
    ProjectFactory(name="Alpha")
    ProjectFactory(name="Beta")
    r = client.get(reverse("projects:list"))
    assert r.status_code == 200
    assert b"Alpha" in r.content
    assert b"Beta" in r.content


def test_list_search_filters_by_name(client, staff_user):
    client.force_login(staff_user)
    ProjectFactory(name="Apollo")
    ProjectFactory(name="Mercury")
    r = client.get(reverse("projects:list") + "?q=apol")
    assert b"Apollo" in r.content
    assert b"Mercury" not in r.content


def test_list_status_filter(client, staff_user):
    client.force_login(staff_user)
    ProjectFactory(name="ActiveOne", status="active")
    ProjectFactory(name="PlanningOne", status="planning")
    r = client.get(reverse("projects:list") + "?status=active")
    assert b"ActiveOne" in r.content
    assert b"PlanningOne" not in r.content


def test_list_archived_excluded(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory(name="Hidden")
    p.archive()
    r = client.get(reverse("projects:list"))
    assert b"Hidden" not in r.content


# ── Detail tabs ────────────────────────────────────────────────────────

def test_overview_renders_with_tabs(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory(name="Tabbed")
    r = client.get(reverse("projects:overview", args=[p.slug]))
    assert r.status_code == 200
    assert b"Tabbed" in r.content
    # All four tab labels present
    assert b"Overview" in r.content
    assert b"Tasks" in r.content
    assert b"Team" in r.content
    assert b"Activity" in r.content


def test_tasks_tab_groups_by_status(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    ProjectTaskFactory(project=p, status="todo", title="T1")
    ProjectTaskFactory(project=p, status="done", title="D1")
    r = client.get(reverse("projects:tasks", args=[p.slug]))
    columns = r.context["columns"]
    by_key = {c["key"]: c for c in columns}
    assert "T1" in [t.title for t in by_key["todo"]["tasks"]]
    assert "D1" in [t.title for t in by_key["done"]["tasks"]]


def test_team_tab_lists_members(client, staff_user):
    client.force_login(staff_user)
    member = UserFactory(first_name="Pat")
    p = ProjectFactory()
    p.team.add(member)
    r = client.get(reverse("projects:team", args=[p.slug]))
    assert r.status_code == 200
    assert b"Pat" in r.content


def test_activity_tab_synthesizes_events(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    ProjectTaskFactory(project=p, status="done", title="X")
    r = client.get(reverse("projects:activity", args=[p.slug]))
    assert b"Task created" in r.content or b"X" in r.content


# ── Create / Edit / Archive ────────────────────────────────────────────

def test_create_assigns_owner_and_team(client, staff_user):
    client.force_login(staff_user)
    r = client.post(reverse("projects:create"), data={
        "name": "Brand New",
        "description": "",
        "status": "active",
        "priority": "med",
        "customer": "",
        "due_date": "",
        "start_date": "",
        "budget": "0",
        "progress": "0",
    })
    assert r.status_code == 302
    new = Project.objects.get(name="Brand New")
    assert new.owner == staff_user
    assert staff_user in new.team.all()


def test_edit_updates_fields(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory(name="Old", status="planning")
    r = client.post(reverse("projects:edit", args=[p.slug]), data={
        "name": "Renamed",
        "description": "",
        "status": "active",
        "priority": "high",
        "customer": "",
        "due_date": "",
        "start_date": "",
        "budget": "0",
        "progress": "0",
    })
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.name == "Renamed"
    assert p.status == "active"


def test_archive_sets_archived_at(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    r = client.post(reverse("projects:archive", args=[p.slug]))
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.archived_at is not None


def test_archive_again_restores(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    p.archive()
    client.post(reverse("projects:archive", args=[p.slug]))
    p.refresh_from_db()
    assert p.archived_at is None


# ── Tasks ──────────────────────────────────────────────────────────────

def test_task_create_appends_position(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    ProjectTaskFactory(project=p, status="todo", position=0)
    r = client.post(reverse("projects:task_create", args=[p.slug]), data={
        "title": "New task", "description": "",
        "status": "todo", "priority": "med",
        "assignee": "", "due_date": "",
    })
    assert r.status_code == 302
    new = ProjectTask.objects.get(title="New task")
    assert new.position == 1


def test_task_toggle_advances_status(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    t = ProjectTaskFactory(project=p, status="todo")
    client.post(reverse("projects:task_toggle", args=[p.slug, t.pk]))
    t.refresh_from_db()
    assert t.status == "in_progress"
    client.post(reverse("projects:task_toggle", args=[p.slug, t.pk]))
    t.refresh_from_db()
    assert t.status == "review"


def test_task_delete_removes_task(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    t = ProjectTaskFactory(project=p)
    r = client.post(reverse("projects:task_delete", args=[p.slug, t.pk]))
    assert r.status_code == 302
    assert not ProjectTask.objects.filter(pk=t.pk).exists()


# ── Milestones ─────────────────────────────────────────────────────────

def test_milestone_create_appends(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    r = client.post(reverse("projects:milestone_create", args=[p.slug]), data={
        "title": "Phase 1", "due_date": "",
    })
    assert r.status_code == 302
    assert Milestone.objects.filter(project=p, title="Phase 1").exists()


def test_milestone_toggle_completes_then_uncompletes(client, staff_user):
    client.force_login(staff_user)
    p = ProjectFactory()
    m = MilestoneFactory(project=p)
    client.post(reverse("projects:milestone_toggle", args=[p.slug, m.pk]))
    m.refresh_from_db()
    assert m.completed_at is not None
    client.post(reverse("projects:milestone_toggle", args=[p.slug, m.pk]))
    m.refresh_from_db()
    assert m.completed_at is None
