import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_register_creates_unverified_user(client):
    mail.outbox = []
    response = client.post("/accounts/register/", {
        "username": "bob",
        "email": "bob@example.com",
        "first_name": "Bob",
        "last_name": "Builder",
        "password1": "testpass-x9!",
        "password2": "testpass-x9!",
    })
    assert response.status_code == 302
    assert response["Location"].endswith("/email/verify/")
    from apps.accounts.models import User
    u = User.objects.get(username="bob")
    assert u.email_verified_at is None
    assert len(mail.outbox) == 1
    assert "verify" in mail.outbox[0].body.lower()
    assert "/email/verify/" in mail.outbox[0].body


def test_verify_prompt_accessible_to_logged_in_unverified_user(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 200
    assert b"Check your email" in response.content or b"check your email" in response.content


def test_verify_prompt_redirects_already_verified_user_home(client):
    user = UserFactory()
    from django.utils import timezone
    user.email_verified_at = timezone.now()
    user.save()
    client.force_login(user)
    response = client.get("/email/verify/")
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_valid_token_marks_verified(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = client.get(f"/email/verify/{uidb64}/{token}/")
    user.refresh_from_db()
    assert user.email_verified_at is not None
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_bad_token_renders_invalid_page(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    response = client.get(f"/email/verify/{uidb64}/not-a-valid-token/")
    assert response.status_code == 200
    assert b"expired" in response.content.lower() or b"invalid" in response.content.lower()
    user.refresh_from_db()
    assert user.email_verified_at is None


def test_confirm_view_idempotent_when_already_verified(client):
    user = UserFactory(email="alice@x.com")
    from django.utils import timezone
    user.email_verified_at = timezone.now()
    user.save()
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    response = client.get(f"/email/verify/{uidb64}/{token}/")
    assert response.status_code == 302
    assert response["Location"] == "/"


def test_confirm_view_with_unknown_uid_renders_invalid_page(client):
    response = client.get("/email/verify/99999999/whatever/")
    assert response.status_code == 200
    assert b"expired" in response.content.lower() or b"invalid" in response.content.lower()


def test_resend_sends_new_email(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    mail.outbox = []
    response = client.post("/email/verify/resend/")
    assert response.status_code == 302
    assert len(mail.outbox) == 1


def test_resend_respects_cooldown(client):
    user = UserFactory(email="alice@x.com")
    user.email_verified_at = None
    user.save()
    client.force_login(user)
    client.post("/email/verify/resend/")
    mail.outbox = []
    # Second immediate resend is rate-gated
    client.post("/email/verify/resend/")
    assert len(mail.outbox) == 0
