import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.files.models import File, Folder
from apps.files.tests.factories import FileFactory, FolderFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def alice():
    return UserFactory(username="alice", is_staff=True)


@pytest.fixture
def bob():
    return UserFactory(username="bob", is_staff=True)


# ----- Access -----

def test_browser_redirects_anonymous(client):
    r = client.get(reverse("files:root"))
    assert r.status_code == 302


def test_browser_forbidden_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("files:root"))
    assert r.status_code == 403


def test_root_browser_shows_owner_root_items(client, alice, bob):
    FolderFactory(owner=alice, parent=None, name="alice_root")
    FolderFactory(owner=bob, parent=None, name="bob_root")
    client.force_login(alice)
    r = client.get(reverse("files:root"))
    assert r.status_code == 200
    assert b"alice_root" in r.content
    assert b"bob_root" not in r.content


def test_folder_browser_shows_folder_contents(client, alice):
    parent = FolderFactory(owner=alice, name="parent")
    FolderFactory(owner=alice, parent=parent, name="child")
    FolderFactory(owner=alice, parent=None, name="sibling")
    client.force_login(alice)
    r = client.get(reverse("files:folder", args=[parent.pk]))
    assert r.status_code == 200
    assert b"child" in r.content
    assert b"sibling" not in r.content


def test_folder_browser_404_cross_user(client, alice, bob):
    f = FolderFactory(owner=bob)
    client.force_login(alice)
    r = client.get(reverse("files:folder", args=[f.pk]))
    assert r.status_code == 404


# ----- Folder CRUD -----

def test_folder_create_assigns_owner(client, alice):
    client.force_login(alice)
    r = client.post(reverse("files:folder_create"), data={"name": "Documents"})
    assert r.status_code == 302
    folder = Folder.objects.get(name="Documents")
    assert folder.owner == alice


def test_folder_delete_removes(client, alice):
    f = FolderFactory(owner=alice)
    client.force_login(alice)
    r = client.post(reverse("files:folder_delete", args=[f.pk]))
    assert r.status_code == 302
    assert not Folder.objects.filter(pk=f.pk).exists()


# ----- Upload -----

def test_upload_creates_file_records(client, alice):
    client.force_login(alice)
    upload = SimpleUploadedFile("test.txt", b"hello", content_type="text/plain")
    r = client.post(reverse("files:upload"), data={"files": upload})
    assert r.status_code == 302
    f = File.objects.get()
    assert f.owner == alice
    assert f.original_name == "test.txt"
    assert f.size == 5
    assert f.content_type == "text/plain"


def test_upload_rejects_oversized_file(client, alice):
    client.force_login(alice)
    big = SimpleUploadedFile("big.bin", b"x" * (11 * 1024 * 1024), content_type="application/octet-stream")
    r = client.post(reverse("files:upload"), data={"files": big})
    assert r.status_code == 302
    assert File.objects.count() == 0


def test_upload_into_folder(client, alice):
    folder = FolderFactory(owner=alice)
    client.force_login(alice)
    upload = SimpleUploadedFile("in_folder.txt", b"x", content_type="text/plain")
    r = client.post(reverse("files:upload"), data={
        "files": upload, "parent": folder.pk,
    })
    assert r.status_code == 302
    f = File.objects.get()
    assert f.folder == folder


# ----- Download -----

def test_download_returns_file_content(client, alice):
    f = FileFactory(owner=alice, original_name="hello.txt")
    client.force_login(alice)
    r = client.get(reverse("files:download", args=[f.pk]))
    assert r.status_code == 200
    assert "attachment" in r["Content-Disposition"]
    assert "hello.txt" in r["Content-Disposition"]


def test_download_404_for_other_users_file(client, alice, bob):
    f = FileFactory(owner=bob)
    client.force_login(alice)
    r = client.get(reverse("files:download", args=[f.pk]))
    assert r.status_code == 404


# ----- Rename -----

def test_file_rename(client, alice):
    f = FileFactory(owner=alice, original_name="old.txt")
    client.force_login(alice)
    r = client.post(reverse("files:file_rename", args=[f.pk]), data={"name": "new.txt"})
    assert r.status_code == 302
    f.refresh_from_db()
    assert f.original_name == "new.txt"


def test_file_delete(client, alice):
    f = FileFactory(owner=alice)
    client.force_login(alice)
    r = client.post(reverse("files:file_delete", args=[f.pk]))
    assert r.status_code == 302
    assert not File.objects.filter(pk=f.pk).exists()
