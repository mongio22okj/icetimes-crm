import pytest

from apps.accounts.tests.factories import UserFactory
from apps.mail.forms import ComposeForm, ReplyForm

pytestmark = pytest.mark.django_db


def test_compose_valid():
    sender = UserFactory(is_staff=True)
    recipient = UserFactory(is_staff=True, username="recip")
    form = ComposeForm(
        data={
            "recipient": recipient.pk,
            "subject": "Hello",
            "body": "Hi there.",
        },
        current_user=sender,
    )
    assert form.is_valid(), form.errors


def test_compose_excludes_self_from_recipient_picker():
    sender = UserFactory(is_staff=True)
    UserFactory(is_staff=True, username="recip")
    form = ComposeForm(current_user=sender)
    pks = list(form.fields["recipient"].queryset.values_list("pk", flat=True))
    assert sender.pk not in pks


def test_compose_recipient_picker_excludes_non_staff():
    sender = UserFactory(is_staff=True)
    UserFactory(is_staff=True, username="staff")
    UserFactory(is_staff=False, username="external")
    form = ComposeForm(current_user=sender)
    usernames = set(form.fields["recipient"].queryset.values_list("username", flat=True))
    assert "staff" in usernames
    assert "external" not in usernames


def test_compose_rejects_empty_subject():
    sender = UserFactory(is_staff=True)
    recipient = UserFactory(is_staff=True, username="recip")
    form = ComposeForm(
        data={"recipient": recipient.pk, "subject": "", "body": "x"},
        current_user=sender,
    )
    assert not form.is_valid()
    assert "subject" in form.errors


def test_reply_valid_with_body():
    form = ReplyForm(data={"body": "OK"})
    assert form.is_valid()


def test_reply_rejects_empty():
    form = ReplyForm(data={"body": ""})
    assert not form.is_valid()
