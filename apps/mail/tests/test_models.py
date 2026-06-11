import pytest

from apps.accounts.tests.factories import UserFactory
from apps.mail.models import Message
from apps.mail.tests.factories import DraftFactory, MessageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice():
    return UserFactory(username="alice")


@pytest.fixture
def bob():
    return UserFactory(username="bob")


# ----- Folder querysets -----

def test_inbox_excludes_drafts_and_trash(alice, bob):
    received = MessageFactory(sender=bob, recipient=alice)
    DraftFactory(sender=alice, recipient=bob)  # not received by alice
    trashed = MessageFactory(sender=bob, recipient=alice, is_trashed=True)

    inbox = Message.objects.inbox_for(alice)
    assert received in inbox
    assert trashed not in inbox


def test_inbox_excludes_others_messages(alice, bob):
    other = UserFactory(username="carol")
    other_msg = MessageFactory(sender=other, recipient=other)
    inbox = Message.objects.inbox_for(alice)
    assert other_msg not in inbox


def test_sent_includes_only_sent_not_drafts(alice, bob):
    sent = MessageFactory(sender=alice, recipient=bob)
    draft = DraftFactory(sender=alice, recipient=bob)
    sent_qs = Message.objects.sent_for(alice)
    assert sent in sent_qs
    assert draft not in sent_qs


def test_drafts_only_drafts(alice, bob):
    sent = MessageFactory(sender=alice, recipient=bob)
    draft = DraftFactory(sender=alice, recipient=bob)
    drafts = Message.objects.drafts_for(alice)
    assert draft in drafts
    assert sent not in drafts


def test_starred_excludes_trashed(alice, bob):
    starred = MessageFactory(sender=bob, recipient=alice, is_starred=True)
    starred_trashed = MessageFactory(
        sender=bob, recipient=alice, is_starred=True, is_trashed=True,
    )
    starred_qs = Message.objects.starred_for(alice)
    assert starred in starred_qs
    assert starred_trashed not in starred_qs


def test_trash_only_trashed_received(alice, bob):
    trashed = MessageFactory(sender=bob, recipient=alice, is_trashed=True)
    not_trashed = MessageFactory(sender=bob, recipient=alice)
    trash_qs = Message.objects.trash_for(alice)
    assert trashed in trash_qs
    assert not_trashed not in trash_qs


def test_folder_counts_returns_correct_counts(alice, bob):
    MessageFactory(sender=bob, recipient=alice, is_read=False)
    MessageFactory(sender=bob, recipient=alice, is_read=True)
    MessageFactory(sender=bob, recipient=alice, is_starred=True)
    MessageFactory(sender=bob, recipient=alice, is_trashed=True)
    MessageFactory(sender=alice, recipient=bob)
    DraftFactory(sender=alice, recipient=bob)

    counts = Message.objects.folder_counts(alice)
    # Alice received 4, 1 trashed → inbox=3
    assert counts["inbox"] == 3
    # Two unread (factory default is_read=False) minus the trashed one
    assert counts["inbox_unread"] == 2
    assert counts["sent"] == 1
    assert counts["drafts"] == 1
    assert counts["starred"] == 1
    assert counts["trash"] == 1


# ----- Threading -----

def test_thread_chain_for_leaf_message(alice, bob):
    msg = MessageFactory(sender=alice, recipient=bob)
    chain = msg.thread_chain()
    assert chain == [msg]


def test_thread_chain_walks_to_root_and_collects_replies(alice, bob):
    root = MessageFactory(sender=alice, recipient=bob, subject="Root")
    reply1 = MessageFactory(sender=bob, recipient=alice, parent=root, subject="Re: Root")
    reply2 = MessageFactory(sender=alice, recipient=bob, parent=reply1, subject="Re2")

    # Calling thread_chain on any node walks to root + collects all
    chain = reply2.thread_chain()
    assert chain[0] == root
    assert reply1 in chain
    assert reply2 in chain
    assert len(chain) == 3
