"""Phase 17 — settings depth panes + audit signals + management commands."""
import io
import zipfile
from datetime import timedelta

import pytest
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import (
    AuditEvent,
    SessionMetadata,
    User,
    record_audit,
)
from apps.accounts.tests.factories import UserFactory
from apps.api.models import APIKey, Webhook

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return UserFactory(is_active=True)


# ── Sessions pane ─────────────────────────────────────────────────────


def _make_session_metadata(user, key="abc1234567890123", ua="Mozilla/5.0 iPhone"):
    Session.objects.create(
        session_key=key, session_data="", expire_date=timezone.now() + timedelta(days=14),
    )
    return SessionMetadata.objects.create(
        session_key=key, user=user, user_agent=ua, ip_address="192.0.2.1",
    )


def test_sessions_pane_lists_only_live_sessions(client, user):
    _make_session_metadata(user, key="alive1234567890")
    # Orphan metadata — Session was deleted out from under it.
    SessionMetadata.objects.create(
        session_key="orphaned1234567", user=user, user_agent="x", ip_address="x",
    )
    client.force_login(user)
    r = client.get(reverse("settings:sessions"))
    sessions = r.context["sessions"]
    keys = {s.session_key for s in sessions}
    assert "alive1234567890" in keys
    # Orphan never appears (no matching live Session).
    assert "orphaned1234567" not in keys


def test_session_metadata_device_label_parses_browser():
    s = SessionMetadata(user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/605.1.15")
    label = s.device_label()
    assert "iPhone" in label
    assert "Safari" in label


def test_revoke_other_sessions_drops_them(client, user):
    other = _make_session_metadata(user, key="otherone1234567")
    client.force_login(user)  # creates the current session
    r = client.post(reverse("settings:revoke_other_sessions"))
    assert r.status_code in (301, 302)
    assert not SessionMetadata.objects.filter(pk=other.pk).exists()
    assert not Session.objects.filter(session_key="otherone1234567").exists()


def test_revoke_other_sessions_records_audit(client, user):
    _make_session_metadata(user, key="otherone1234567")
    client.force_login(user)
    client.post(reverse("settings:revoke_other_sessions"))
    assert AuditEvent.objects.filter(user=user, kind="session_revoked").exists()


def test_revoke_specific_session(client, user):
    target = _make_session_metadata(user, key="killmenow123456")
    client.force_login(user)
    client.post(reverse("settings:revoke_session", args=[target.session_key]))
    assert not SessionMetadata.objects.filter(pk=target.pk).exists()


def test_revoke_session_404s_for_other_users(client, user):
    other = UserFactory()
    target = _make_session_metadata(other, key="theirsession123")
    client.force_login(user)
    r = client.post(reverse("settings:revoke_session", args=[target.session_key]))
    assert r.status_code == 404


# ── API tokens pane ───────────────────────────────────────────────────


def test_api_tokens_pane_lists_user_keys(client, user):
    APIKey.generate(user, "k1")
    APIKey.generate(user, "k2")
    client.force_login(user)
    r = client.get(reverse("settings:api_tokens"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "k1" in body
    assert "k2" in body


def test_create_api_token_via_form_creates_and_reveals_once(client, user):
    client.force_login(user)
    r = client.post(reverse("settings:api_tokens"), {"name": "From form"})
    assert r.status_code in (301, 302)
    # Follow redirect — the just-created banner should show the raw key.
    r2 = client.get(reverse("settings:api_tokens"))
    body = r2.content.decode()
    assert "API key created" in body
    # Banner contains the apex_ prefix
    assert "apex_" in body
    # Subsequent visit no longer shows the raw key.
    r3 = client.get(reverse("settings:api_tokens"))
    body3 = r3.content.decode()
    assert "API key created" not in body3


def test_create_api_token_records_audit(client, user):
    client.force_login(user)
    client.post(reverse("settings:api_tokens"), {"name": "Audited"})
    assert AuditEvent.objects.filter(user=user, kind="api_key_created").exists()


def test_revoke_api_token(client, user):
    instance, _ = APIKey.generate(user, "doomed")
    client.force_login(user)
    client.post(reverse("settings:revoke_api_token", args=[instance.pk]))
    instance.refresh_from_db()
    assert instance.revoked_at is not None
    assert AuditEvent.objects.filter(user=user, kind="api_key_revoked").exists()


def test_revoke_api_token_only_owner(client, user):
    other = UserFactory()
    instance, _ = APIKey.generate(other, "theirs")
    client.force_login(user)
    r = client.post(reverse("settings:revoke_api_token", args=[instance.pk]))
    assert r.status_code == 404


# ── Webhooks pane ─────────────────────────────────────────────────────


def test_webhooks_pane_lists_user_webhooks(client, user):
    Webhook.objects.create(user=user, url="https://x.example",
                           events="invoice.paid", secret="s")
    client.force_login(user)
    r = client.get(reverse("settings:webhooks"))
    assert "x.example" in r.content.decode()


def test_create_webhook_via_form(client, user):
    client.force_login(user)
    r = client.post(reverse("settings:webhooks"), {
        "name": "Production",
        "url": "https://prod.example.com/hook",
        "events": ["invoice.paid", "invoice.sent"],
    })
    assert r.status_code in (301, 302)
    w = Webhook.objects.get(user=user)
    assert w.name == "Production"
    assert "invoice.paid" in w.events
    assert "invoice.sent" in w.events


def test_create_webhook_requires_url_and_events(client, user):
    client.force_login(user)
    # No URL
    client.post(reverse("settings:webhooks"), {"events": ["invoice.paid"]})
    assert not Webhook.objects.filter(user=user).exists()
    # No events
    client.post(reverse("settings:webhooks"), {"url": "https://x.example"})
    assert not Webhook.objects.filter(user=user).exists()


def test_create_webhook_reveals_secret_once(client, user):
    client.force_login(user)
    client.post(reverse("settings:webhooks"), {
        "url": "https://x.example", "events": ["invoice.paid"],
    })
    r = client.get(reverse("settings:webhooks"))
    assert "Webhook created" in r.content.decode()


def test_delete_webhook_only_owner(client, user):
    other = UserFactory()
    w = Webhook.objects.create(user=other, url="https://x.example",
                               events="invoice.paid", secret="s")
    client.force_login(user)
    r = client.post(reverse("settings:delete_webhook", args=[w.pk]))
    assert r.status_code == 404
    assert Webhook.objects.filter(pk=w.pk).exists()


# ── Audit log + signals ───────────────────────────────────────────────


def test_audit_log_renders_user_events(client, user):
    record_audit(user, "login", description="Test login")
    record_audit(user, "password_changed", description="Test pwd")
    client.force_login(user)
    r = client.get(reverse("settings:audit_log"))
    body = r.content.decode()
    assert "Test login" in body
    assert "Test pwd" in body


def test_audit_log_scoped_to_user(client, user):
    other = UserFactory()
    record_audit(other, "login", description="THEIRS")
    client.force_login(user)
    r = client.get(reverse("settings:audit_log"))
    assert "THEIRS" not in r.content.decode()


def test_login_signal_records_audit(client):
    user = UserFactory(is_active=True)
    user.set_password("password123")
    user.save()
    client.post(reverse("login"), {
        "username": user.username, "password": "password123",
    })
    assert AuditEvent.objects.filter(user=user, kind="login").exists()


def test_failed_login_signal_records_audit(client):
    user = UserFactory(is_active=True)
    user.set_password("rightpass")
    user.save()
    client.post(reverse("login"), {
        "username": user.username, "password": "wrongpass",
    })
    assert AuditEvent.objects.filter(user=user, kind="login_failed").exists()


def test_record_audit_anonymous_returns_none():
    from django.contrib.auth.models import AnonymousUser
    assert record_audit(AnonymousUser(), "login") is None


# ── Data export pane ──────────────────────────────────────────────────


def test_data_export_returns_zip(client, user):
    client.force_login(user)
    r = client.post(reverse("settings:data_export"))
    assert r.status_code == 200
    assert r["Content-Type"] == "application/zip"
    # Open the ZIP and verify expected files exist.
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert any(n.endswith("/user.json") for n in names)
    assert any(n.endswith("/notifications.json") for n in names)
    assert any(n.endswith("/audit_events.json") for n in names)
    assert any(n.endswith("/api_keys.json") for n in names)
    assert any(n.endswith("/webhooks.json") for n in names)


def test_data_export_does_not_include_raw_api_secrets(client, user):
    instance, raw = APIKey.generate(user, "secret-key")
    client.force_login(user)
    r = client.post(reverse("settings:data_export"))
    # The raw key + the SHA-256 hash must NOT appear in the export.
    assert raw.encode() not in r.content
    assert instance.key_hash.encode() not in r.content


def test_data_export_records_audit(client, user):
    client.force_login(user)
    client.post(reverse("settings:data_export"))
    assert AuditEvent.objects.filter(user=user, kind="data_export_requested").exists()


# ── Account deletion ──────────────────────────────────────────────────


def test_request_deletion_with_confirm_phrase_marks_pending(client, user):
    client.force_login(user)
    r = client.post(reverse("settings:account_deletion"), {
        "action": "request",
        "confirm": "delete my account",
    })
    assert r.status_code in (301, 302)
    user.refresh_from_db()
    assert user.is_pending_deletion
    assert user.is_active is False


def test_request_deletion_without_phrase_does_nothing(client, user):
    client.force_login(user)
    client.post(reverse("settings:account_deletion"), {
        "action": "request",
        "confirm": "wrong phrase",
    })
    user.refresh_from_db()
    assert not user.is_pending_deletion
    assert user.is_active is True


def test_request_deletion_records_audit(client, user):
    client.force_login(user)
    client.post(reverse("settings:account_deletion"), {
        "action": "request",
        "confirm": "delete my account",
    })
    assert AuditEvent.objects.filter(user=user, kind="account_deletion_requested").exists()


def test_cancel_deletion_clears_pending(client, user):
    user.pending_deletion_at = timezone.now()
    user.save()
    client.force_login(user)
    client.post(reverse("settings:account_deletion"), {"action": "cancel"})
    user.refresh_from_db()
    assert user.pending_deletion_at is None
    assert AuditEvent.objects.filter(user=user, kind="account_deletion_canceled").exists()


# ── Management commands ──────────────────────────────────────────────


def test_process_pending_deletions_command_deletes_past_grace():
    user = UserFactory(is_active=False)
    user.pending_deletion_at = timezone.now() - timedelta(days=31)
    user.save()
    call_command("process_pending_deletions", "--grace-days", "30")
    assert not User.objects.filter(pk=user.pk).exists()


def test_process_pending_deletions_skips_within_grace():
    user = UserFactory(is_active=False)
    user.pending_deletion_at = timezone.now() - timedelta(days=5)
    user.save()
    call_command("process_pending_deletions", "--grace-days", "30")
    assert User.objects.filter(pk=user.pk).exists()


def test_process_pending_deletions_dry_run_doesnt_delete():
    user = UserFactory(is_active=False)
    user.pending_deletion_at = timezone.now() - timedelta(days=60)
    user.save()
    call_command("process_pending_deletions", "--grace-days", "30", "--dry-run")
    assert User.objects.filter(pk=user.pk).exists()


def test_cleanup_session_metadata_command_removes_orphans(user):
    SessionMetadata.objects.create(
        session_key="orphan_abc", user=user, user_agent="x", ip_address="1.1.1.1",
    )
    # Create a live one — should survive.
    Session.objects.create(
        session_key="alive_xyz", session_data="",
        expire_date=timezone.now() + timedelta(days=14),
    )
    SessionMetadata.objects.create(
        session_key="alive_xyz", user=user, user_agent="x", ip_address="1.1.1.1",
    )
    call_command("cleanup_session_metadata")
    assert not SessionMetadata.objects.filter(session_key="orphan_abc").exists()
    assert SessionMetadata.objects.filter(session_key="alive_xyz").exists()
