import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.chat.models import ChatMessage
from apps.chat.tests.factories import ChatMessageFactory
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice():
    return UserFactory(username="alice", is_staff=True)


@pytest.fixture
def bob():
    return UserFactory(username="bob", is_staff=True)


# ----- Access -----

def test_home_redirects_anonymous(client):
    r = client.get(reverse("chat:home"))
    assert r.status_code == 302
    assert "login" in r.url


def test_home_forbidden_for_non_staff(client):
    user = UserFactory(is_staff=False)
    client.force_login(user)
    r = client.get(reverse("chat:home"))
    assert r.status_code == 403


def test_home_ok_for_staff(client, alice):
    client.force_login(alice)
    r = client.get(reverse("chat:home"))
    assert r.status_code == 200


# ----- Conversation -----

def test_conversation_marks_received_messages_read(client, alice, bob):
    client.force_login(alice)
    msg = ChatMessageFactory(sender=bob, recipient=alice, is_read=False)
    r = client.get(reverse("chat:conversation", args=[bob.pk]))
    assert r.status_code == 200
    msg.refresh_from_db()
    assert msg.is_read is True


def test_conversation_does_not_mark_outgoing_read(client, alice, bob):
    """Sender doesn't get read flipped when revisiting their sent messages."""
    client.force_login(alice)
    sent = ChatMessageFactory(sender=alice, recipient=bob, is_read=False)
    client.get(reverse("chat:conversation", args=[bob.pk]))
    sent.refresh_from_db()
    assert sent.is_read is False  # alice is sender, not recipient


def test_conversation_404_when_partner_is_self(client, alice):
    client.force_login(alice)
    r = client.get(reverse("chat:conversation", args=[alice.pk]))
    assert r.status_code == 404


def test_conversation_404_when_partner_non_staff(client, alice):
    not_staff = UserFactory(is_staff=False)
    client.force_login(alice)
    r = client.get(reverse("chat:conversation", args=[not_staff.pk]))
    assert r.status_code == 404


# ----- Send -----

def test_send_creates_message_and_notification(client, alice, bob):
    client.force_login(alice)
    r = client.post(reverse("chat:send", args=[bob.pk]), data={"body": "Hi Bob!"})
    assert r.status_code == 302
    msg = ChatMessage.objects.get()
    assert msg.sender == alice and msg.recipient == bob
    assert msg.body == "Hi Bob!"
    assert Notification.objects.filter(
        recipient=bob, kind="new_chat",
    ).exists()


def test_send_empty_body_no_message(client, alice, bob):
    client.force_login(alice)
    r = client.post(reverse("chat:send", args=[bob.pk]), data={"body": "   "})
    assert r.status_code == 302
    assert ChatMessage.objects.count() == 0


def test_send_truncates_very_long_body(client, alice, bob):
    client.force_login(alice)
    long = "x" * 3000
    client.post(reverse("chat:send", args=[bob.pk]), data={"body": long})
    msg = ChatMessage.objects.get()
    assert len(msg.body) == 2000


# ----- Stream (HTMX) -----

def test_stream_returns_partial(client, alice, bob):
    client.force_login(alice)
    ChatMessageFactory(sender=bob, recipient=alice, body="Hi Alice")
    r = client.get(reverse("chat:stream", args=[bob.pk]))
    assert r.status_code == 200
    assert b"chat-stream" in r.content
    assert b"Hi Alice" in r.content


def test_stream_marks_unread_received_as_read(client, alice, bob):
    client.force_login(alice)
    msg = ChatMessageFactory(sender=bob, recipient=alice, is_read=False)
    client.get(reverse("chat:stream", args=[bob.pk]))
    msg.refresh_from_db()
    assert msg.is_read is True


# ----- New conversation picker -----

def test_new_lists_staff_candidates(client, alice, bob):
    client.force_login(alice)
    r = client.get(reverse("chat:new"))
    assert r.status_code == 200
    # Link to bob's conversation page should appear
    assert reverse("chat:conversation", args=[bob.pk]).encode() in r.content
