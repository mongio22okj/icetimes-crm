import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.mail.models import Message
from apps.mail.tests.factories import DraftFactory, MessageFactory
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice():
    return UserFactory(username="alice", is_staff=True)


@pytest.fixture
def bob():
    return UserFactory(username="bob", is_staff=True)


# ----- Access control -----

def test_inbox_redirects_anonymous(client):
    r = client.get(reverse("mail:inbox"))
    assert r.status_code == 302
    assert "login" in r.url


def test_inbox_forbidden_for_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("mail:inbox"))
    assert r.status_code == 403


# ----- Folders -----

def test_inbox_shows_only_received(client, alice, bob):
    client.force_login(alice)
    received = MessageFactory(sender=bob, recipient=alice, subject="ToAlice")
    sent = MessageFactory(sender=alice, recipient=bob, subject="FromAlice")
    r = client.get(reverse("mail:inbox"))
    assert r.status_code == 200
    assert b"ToAlice" in r.content
    assert b"FromAlice" not in r.content


def test_sent_shows_outgoing(client, alice, bob):
    client.force_login(alice)
    MessageFactory(sender=alice, recipient=bob, subject="MySent")
    r = client.get(reverse("mail:sent"))
    assert r.status_code == 200
    assert b"MySent" in r.content


def test_drafts_shows_unsent(client, alice, bob):
    client.force_login(alice)
    DraftFactory(sender=alice, recipient=bob, subject="MyDraftSubject")
    MessageFactory(sender=alice, recipient=bob, subject="AlreadySentSubject")
    r = client.get(reverse("mail:drafts"))
    assert r.status_code == 200
    assert b"MyDraftSubject" in r.content
    assert b"AlreadySentSubject" not in r.content


# ----- Compose -----

def test_compose_get_returns_form(client, alice):
    client.force_login(alice)
    r = client.get(reverse("mail:compose"))
    assert r.status_code == 200
    assert b"Subject" in r.content or b"subject" in r.content


def test_compose_post_send_creates_message_and_notification(client, alice, bob):
    client.force_login(alice)
    payload = {
        "recipient": bob.pk,
        "subject": "Hello Bob",
        "body": "Long time no see.",
    }
    r = client.post(reverse("mail:compose"), data=payload)
    assert r.status_code == 302
    msg = Message.objects.get()
    assert msg.sender == alice and msg.recipient == bob
    assert msg.sent_at is not None
    # Notification fired to bob
    assert Notification.objects.filter(
        recipient=bob, kind="new_mail",
    ).exists()


def test_compose_post_save_draft_no_notification(client, alice, bob):
    client.force_login(alice)
    payload = {
        "recipient": bob.pk,
        "subject": "Drafted",
        "body": "WIP",
        "save_draft": "1",
    }
    Notification.objects.filter(kind="new_mail").delete()
    r = client.post(reverse("mail:compose"), data=payload)
    assert r.status_code == 302
    msg = Message.objects.get()
    assert msg.sent_at is None
    assert not Notification.objects.filter(kind="new_mail").exists()


# ----- Thread / read state -----

def test_thread_marks_unread_message_read_for_recipient(client, alice, bob):
    client.force_login(alice)
    msg = MessageFactory(sender=bob, recipient=alice, is_read=False)
    r = client.get(reverse("mail:thread", args=[msg.pk]))
    assert r.status_code == 200
    msg.refresh_from_db()
    assert msg.is_read is True


def test_thread_does_not_mark_read_for_sender(client, alice, bob):
    client.force_login(alice)
    msg = MessageFactory(sender=alice, recipient=bob, is_read=False)
    r = client.get(reverse("mail:thread", args=[msg.pk]))
    assert r.status_code == 200
    msg.refresh_from_db()
    assert msg.is_read is False


def test_thread_404_for_unrelated_user(client, alice, bob):
    other = UserFactory(username="carol", is_staff=True)
    msg = MessageFactory(sender=alice, recipient=bob)
    client.force_login(other)
    r = client.get(reverse("mail:thread", args=[msg.pk]))
    assert r.status_code == 404


# ----- Star / Trash -----

def test_star_toggle(client, alice, bob):
    client.force_login(alice)
    msg = MessageFactory(sender=bob, recipient=alice)
    client.post(reverse("mail:star", args=[msg.pk]))
    msg.refresh_from_db()
    assert msg.is_starred is True
    client.post(reverse("mail:star", args=[msg.pk]))
    msg.refresh_from_db()
    assert msg.is_starred is False


def test_trash_toggle(client, alice, bob):
    client.force_login(alice)
    msg = MessageFactory(sender=bob, recipient=alice)
    client.post(reverse("mail:trash_toggle", args=[msg.pk]))
    msg.refresh_from_db()
    assert msg.is_trashed is True
    # Now in trash, untrashing restores
    client.post(reverse("mail:trash_toggle", args=[msg.pk]))
    msg.refresh_from_db()
    assert msg.is_trashed is False


def test_star_404_for_non_recipient(client, alice, bob):
    other = UserFactory(username="carol", is_staff=True)
    msg = MessageFactory(sender=alice, recipient=bob)
    client.force_login(other)
    r = client.post(reverse("mail:star", args=[msg.pk]))
    assert r.status_code == 404


# ----- Reply -----

def test_reply_creates_child_message(client, alice, bob):
    client.force_login(alice)
    parent = MessageFactory(sender=bob, recipient=alice, subject="Question")
    r = client.post(reverse("mail:reply", args=[parent.pk]), data={"body": "Answer"})
    assert r.status_code == 302
    reply = Message.objects.get(parent=parent)
    assert reply.sender == alice and reply.recipient == bob
    assert reply.subject.startswith("Re:")
    assert reply.body == "Answer"


# ----- Drafts -----

def test_draft_edit_loads_form_with_instance(client, alice, bob):
    client.force_login(alice)
    draft = DraftFactory(sender=alice, recipient=bob, subject="MyDraft")
    r = client.get(reverse("mail:draft_edit", args=[draft.pk]))
    assert r.status_code == 200
    assert b"MyDraft" in r.content


def test_draft_discard(client, alice, bob):
    client.force_login(alice)
    draft = DraftFactory(sender=alice, recipient=bob)
    r = client.post(reverse("mail:draft_discard", args=[draft.pk]))
    assert r.status_code == 302
    assert not Message.objects.filter(pk=draft.pk).exists()
