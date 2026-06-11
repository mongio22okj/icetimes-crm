import pytest

from apps.accounts.tests.factories import UserFactory
from apps.chat.models import ChatMessage
from apps.chat.tests.factories import ChatMessageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice():
    return UserFactory(username="alice")


@pytest.fixture
def bob():
    return UserFactory(username="bob")


@pytest.fixture
def carol():
    return UserFactory(username="carol")


def test_conversation_for_returns_both_directions_chronologically(alice, bob):
    m1 = ChatMessageFactory(sender=alice, recipient=bob, body="hi bob")
    m2 = ChatMessageFactory(sender=bob, recipient=alice, body="hi alice")
    chain = list(ChatMessage.objects.conversation_for(alice, bob))
    assert chain == [m1, m2]


def test_conversation_excludes_other_users(alice, bob, carol):
    ChatMessageFactory(sender=alice, recipient=bob, body="for bob")
    ChatMessageFactory(sender=alice, recipient=carol, body="for carol")
    chain = list(ChatMessage.objects.conversation_for(alice, bob))
    bodies = [m.body for m in chain]
    assert "for bob" in bodies
    assert "for carol" not in bodies


def test_unread_from_filter(alice, bob):
    unread = ChatMessageFactory(sender=bob, recipient=alice, is_read=False)
    read = ChatMessageFactory(sender=bob, recipient=alice, is_read=True)
    qs = ChatMessage.objects.unread_from(bob, alice)
    assert unread in qs
    assert read not in qs


def test_partners_for_lists_all_partners_with_unread_count(alice, bob, carol):
    ChatMessageFactory(sender=bob, recipient=alice, is_read=False)
    ChatMessageFactory(sender=bob, recipient=alice, is_read=False)
    ChatMessageFactory(sender=alice, recipient=carol)
    rows = ChatMessage.objects.partners_for(alice)
    by_partner = {r["partner"].username: r for r in rows}
    assert "bob" in by_partner
    assert "carol" in by_partner
    assert by_partner["bob"]["unread_count"] == 2
    assert by_partner["carol"]["unread_count"] == 0


def test_partners_for_sorted_by_last_message_desc(alice, bob, carol):
    # Bob first, then carol → carol should sort first
    ChatMessageFactory(sender=alice, recipient=bob)
    ChatMessageFactory(sender=alice, recipient=carol)
    rows = ChatMessage.objects.partners_for(alice)
    assert rows[0]["partner"].username == "carol"
    assert rows[1]["partner"].username == "bob"


def test_partners_for_empty_when_no_messages(alice):
    assert ChatMessage.objects.partners_for(alice) == []
