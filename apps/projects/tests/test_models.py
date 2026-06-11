import pytest
from django.utils import timezone

from apps.projects.models import Project
from apps.projects.tests.factories import (
    MilestoneFactory,
    ProjectFactory,
    ProjectTaskFactory,
)

pytestmark = pytest.mark.django_db


def test_slug_auto_generated_from_name():
    p = ProjectFactory(name="My Cool Project")
    assert p.slug == "my-cool-project"


def test_slug_uniqueness_with_suffix():
    ProjectFactory(name="Apex")
    p2 = ProjectFactory(name="Apex")
    assert p2.slug == "apex-2"


def test_archive_hides_from_default_manager():
    p = ProjectFactory()
    p.archive()
    assert Project.objects.filter(pk=p.pk).count() == 0
    assert Project.all_objects.filter(pk=p.pk).count() == 1


def test_restore_unarchives():
    p = ProjectFactory()
    p.archive()
    p.restore()
    assert p.archived_at is None
    assert Project.objects.filter(pk=p.pk).exists()


def test_task_count_properties():
    p = ProjectFactory()
    ProjectTaskFactory.create_batch(3, project=p, status="todo")
    ProjectTaskFactory.create_batch(2, project=p, status="done")
    assert p.task_count == 5
    assert p.completed_task_count == 2
    assert p.open_task_count == 3


def test_computed_progress_uses_task_completion():
    p = ProjectFactory(progress=10)
    ProjectTaskFactory.create_batch(2, project=p, status="todo")
    ProjectTaskFactory.create_batch(2, project=p, status="done")
    # 2/4 = 50%
    assert p.computed_progress == 50


def test_computed_progress_falls_back_to_field_when_no_tasks():
    p = ProjectFactory(progress=42)
    assert p.computed_progress == 42


def test_milestone_mark_complete_idempotent():
    m = MilestoneFactory()
    assert not m.is_completed
    m.mark_complete()
    first = m.completed_at
    m.mark_complete()
    assert m.completed_at == first


def test_milestone_mark_incomplete_clears_timestamp():
    m = MilestoneFactory()
    m.mark_complete()
    m.mark_incomplete()
    assert m.completed_at is None


def test_project_str_returns_name():
    p = ProjectFactory(name="Hello")
    assert str(p) == "Hello"


def test_archived_at_set_to_now_on_archive():
    p = ProjectFactory()
    p.archive()
    assert p.archived_at is not None
    assert (timezone.now() - p.archived_at).total_seconds() < 5
