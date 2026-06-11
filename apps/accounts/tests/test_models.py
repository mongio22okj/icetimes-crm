import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_model_is_custom():
    assert User._meta.app_label == "accounts"


@pytest.mark.django_db
def test_user_has_full_name_helper():
    user = User.objects.create_user(username="alice", email="a@b.co", first_name="Alice", last_name="Adams")
    assert user.get_full_name() == "Alice Adams"


@pytest.mark.django_db
def test_user_has_avatar_field():
    user = User.objects.create_user(username="bob", email="b@b.co")
    assert hasattr(user, "avatar")


@pytest.mark.django_db
def test_user_has_role_field_with_default():
    user = User.objects.create_user(username="carol", email="c@b.co")
    assert user.role == "staff"
