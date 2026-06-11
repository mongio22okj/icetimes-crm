import pytest

from apps.accounts.tests.factories import UserFactory
from apps.projects.tests.factories import ProjectFactory, ProjectTaskFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def viewer():
    return UserFactory()


# ── Auth gates ────────────────────────────────────────────────────────

def test_list_redirects_anonymous(client):
    r = client.get("/people/")
    assert r.status_code == 302


def test_overview_redirects_anonymous(client):
    UserFactory(username="alice")
    r = client.get("/people/alice/")
    assert r.status_code == 302


# ── Directory ─────────────────────────────────────────────────────────

def test_list_renders_active_users(client, viewer):
    client.force_login(viewer)
    UserFactory(username="alpha", first_name="Alpha")
    UserFactory(username="beta", first_name="Beta")
    r = client.get("/people/")
    assert r.status_code == 200
    assert b"Alpha" in r.content
    assert b"Beta" in r.content


def test_list_search_filters_by_name(client, viewer):
    client.force_login(viewer)
    UserFactory(first_name="Apollo", username="apollo")
    UserFactory(first_name="Mercury", username="mercury")
    r = client.get("/people/?q=apol")
    assert b"Apollo" in r.content
    assert b"Mercury" not in r.content


def test_list_search_includes_title(client, viewer):
    client.force_login(viewer)
    u = UserFactory(first_name="Sara", title="Senior Engineer")
    UserFactory(first_name="Mark", title="Sales Lead")
    r = client.get("/people/?q=engineer")
    assert b"Sara" in r.content


def test_list_role_filter(client, viewer):
    client.force_login(viewer)
    UserFactory(first_name="Adam", role="admin")
    UserFactory(first_name="Mia", role="staff")
    r = client.get("/people/?role=admin")
    assert b"Adam" in r.content
    # Staff still gets viewer themselves; assert at least filter applied
    assert b"Mia" not in r.content


def test_list_inactive_users_excluded(client, viewer):
    client.force_login(viewer)
    UserFactory(first_name="Ghost", is_active=False)
    r = client.get("/people/")
    assert b"Ghost" not in r.content


def test_list_counts_in_context(client, viewer):
    client.force_login(viewer)
    UserFactory(role="admin")
    UserFactory(role="manager")
    UserFactory(role="staff")
    r = client.get("/people/")
    counts = r.context["counts"]
    assert counts["total"] >= 4  # viewer + 3
    assert counts["admin"] >= 1
    assert counts["manager"] >= 1


# ── Detail tabs ───────────────────────────────────────────────────────

def test_overview_renders_with_all_tabs(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="alice", first_name="Alice")
    r = client.get(f"/people/{person.username}/")
    assert r.status_code == 200
    assert b"Alice" in r.content
    # All four tab labels visible
    assert b"Overview" in r.content
    assert b"Projects" in r.content
    assert b"Activity" in r.content
    assert b"Connections" in r.content


def test_overview_shows_recent_projects_when_team_member(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="bob")
    p = ProjectFactory(name="Visible Project")
    p.team.add(person)
    r = client.get(f"/people/{person.username}/")
    assert b"Visible Project" in r.content


def test_projects_tab_lists_owned_and_member_projects(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="carol")
    owned = ProjectFactory(name="OwnedOne", owner=person)
    member = ProjectFactory(name="MemberOne")
    member.team.add(person)
    other = ProjectFactory(name="UnrelatedOne")
    r = client.get(f"/people/{person.username}/projects/")
    assert r.status_code == 200
    assert b"OwnedOne" in r.content
    assert b"MemberOne" in r.content
    assert b"UnrelatedOne" not in r.content


def test_activity_tab_synthesizes_events(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="dan")
    p = ProjectFactory(owner=person)
    ProjectTaskFactory(project=p, assignee=person, title="WidgetTask", status="done")
    r = client.get(f"/people/{person.username}/activity/")
    assert b"WidgetTask" in r.content
    # Should include at least one event marker
    assert b"timeline" in r.content.lower() or b"Activity" in r.content


def test_connections_tab_lists_shared_teammates(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="eve")
    teammate = UserFactory(username="fox", first_name="Fox")
    other = UserFactory(username="gus", first_name="Gus")
    p = ProjectFactory()
    p.team.add(person)
    p.team.add(teammate)
    r = client.get(f"/people/{person.username}/connections/")
    assert b"Fox" in r.content
    assert b"Gus" not in r.content


def test_connections_tab_excludes_self(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="hank", first_name="HankSelf")
    p = ProjectFactory()
    p.team.add(person)
    r = client.get(f"/people/{person.username}/connections/")
    # Their own name appears in the header but not in the connections list.
    # Assert via context to be precise.
    assert person not in list(r.context["connections"])


def test_unknown_username_404s(client, viewer):
    client.force_login(viewer)
    r = client.get("/people/nonexistent/")
    assert r.status_code == 404


# ── Header KPI counts ──────────────────────────────────────────────────

def test_header_counts_correct(client, viewer):
    client.force_login(viewer)
    person = UserFactory(username="ivy")
    p1 = ProjectFactory(owner=person)
    p2 = ProjectFactory()
    p2.team.add(person)
    ProjectTaskFactory(project=p1, assignee=person)
    ProjectTaskFactory(project=p1, assignee=person)
    teammate = UserFactory()
    p2.team.add(teammate)
    r = client.get(f"/people/{person.username}/")
    assert r.context["project_count"] == 2
    assert r.context["task_count"] == 2
    assert r.context["team_count"] == 1  # teammate, excludes self
