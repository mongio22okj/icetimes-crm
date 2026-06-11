import pytest
from django.db import IntegrityError

from apps.files.models import File
from apps.files.tests.factories import FileFactory, FolderFactory

pytestmark = pytest.mark.django_db


def test_ancestors_returns_root_to_parent_in_order():
    user_owner = FolderFactory().owner
    root = FolderFactory(owner=user_owner, name="root", parent=None)
    a = FolderFactory(owner=user_owner, name="a", parent=root)
    b = FolderFactory(owner=user_owner, name="b", parent=a)

    assert b.ancestors() == [root, a]


def test_ancestors_empty_for_root_folder():
    f = FolderFactory(parent=None)
    assert f.ancestors() == []


def test_unique_name_per_parent_constraint():
    parent = FolderFactory()
    FolderFactory(owner=parent.owner, parent=parent, name="child")
    with pytest.raises(IntegrityError):
        FolderFactory(owner=parent.owner, parent=parent, name="child")


def test_file_delete_removes_storage(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    f = FileFactory()
    storage_path = f.file.path
    import os
    assert os.path.exists(storage_path)
    f.delete()
    assert not os.path.exists(storage_path)
    assert not File.objects.filter(pk=f.pk).exists()
