import pytest

from apps.accounts.forms import ProfileForm, RegisterForm
from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_register_form_rejects_duplicate_email_case_insensitive():
    UserFactory(email="alice@example.com")
    form = RegisterForm(data={
        "username": "bob",
        "email": "Alice@EXAMPLE.com",
        "first_name": "Bob",
        "last_name": "Builder",
        "password1": "testpass-x9!",
        "password2": "testpass-x9!",
    })
    assert not form.is_valid()
    assert "email" in form.errors


def test_profile_form_rejects_duplicate_email_case_insensitive():
    UserFactory(email="alice@example.com")
    other = UserFactory(email="bob@example.com")
    form = ProfileForm(data={
        "first_name": other.first_name,
        "last_name": other.last_name,
        "email": "Alice@EXAMPLE.com",
        "bio": "",
    }, instance=other)
    assert not form.is_valid()
    assert "email" in form.errors


def test_profile_form_allows_unchanged_email_for_same_user():
    user = UserFactory(email="alice@example.com")
    form = ProfileForm(data={
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": "Alice@EXAMPLE.com",  # same email, different case
        "bio": "",
    }, instance=user)
    assert form.is_valid(), form.errors
