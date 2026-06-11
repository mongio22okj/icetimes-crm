"""Phase 13 — preferences, archive, push subscriptions, dispatch matrix."""
import json

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.notifications.dispatch import notify
from apps.notifications.models import (
    Notification,
    NotificationPreference,
    PushSubscription,
    get_effective_pref,
)
from apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(db):
    return UserFactory(is_staff=True, is_active=True)


# ── get_effective_pref ────────────────────────────────────────────────


def test_effective_pref_falls_back_to_defaults_for_unset_user():
    user = UserFactory()
    # Default for "billing" / email is True per CHANNEL_DEFAULTS.
    assert get_effective_pref(user, "billing", "email") is True
    # Default for "system" / email is False.
    assert get_effective_pref(user, "system", "email") is False


def test_effective_pref_respects_explicit_setting():
    user = UserFactory()
    NotificationPreference.objects.create(
        user=user, category="billing", in_app=True, email=False, push=False,
    )
    assert get_effective_pref(user, "billing", "email") is False


def test_effective_pref_anonymous_returns_false():
    from django.contrib.auth.models import AnonymousUser
    assert get_effective_pref(AnonymousUser(), "system", "in_app") is False


def test_effective_pref_unknown_channel_returns_false():
    user = UserFactory()
    assert get_effective_pref(user, "system", "telegram") is False


# ── notify() honors preferences ───────────────────────────────────────


def test_notify_creates_in_app_when_pref_on():
    user = UserFactory()
    n = notify(recipient=user, category="system", title="Hello")
    assert n is not None
    assert Notification.objects.filter(recipient=user).count() == 1


def test_notify_skips_in_app_when_pref_off():
    user = UserFactory()
    NotificationPreference.objects.create(
        user=user, category="system", in_app=False, email=False, push=False,
    )
    n = notify(recipient=user, category="system", title="Skipped")
    assert n is None
    assert Notification.objects.filter(recipient=user).count() == 0


def test_notify_records_actor_when_provided():
    me = UserFactory()
    actor = UserFactory()
    n = notify(recipient=me, category="mention", title="x", actor=actor)
    assert n.actor == actor


# ── Notification.archive() ────────────────────────────────────────────


def test_archive_marks_archived_at():
    n = NotificationFactory()
    n.archive()
    assert n.archived_at is not None


def test_archive_implies_read_when_unread():
    n = NotificationFactory()
    assert n.read_at is None
    n.archive()
    assert n.read_at is not None


def test_active_queryset_excludes_archived():
    user = UserFactory()
    keep = NotificationFactory(recipient=user)
    drop = NotificationFactory(recipient=user)
    drop.archive()
    pks = set(user.notifications.active().values_list("pk", flat=True))
    assert keep.pk in pks
    assert drop.pk not in pks


# ── List view filters ────────────────────────────────────────────────


def test_list_filters_by_category(client, staff):
    """The bell context processor leaks recent items into every page,
    so we use the queryset attached to the response context — that's
    the actual filtered list, untouched by the bell."""
    NotificationFactory(recipient=staff, category="billing", title="Billing-1")
    NotificationFactory(recipient=staff, category="mention", title="Mention-1")
    client.force_login(staff)
    r = client.get(reverse("notifications:list") + "?category=billing")
    titles = list(r.context["notifications"].values_list("title", flat=True))
    assert "Billing-1" in titles
    assert "Mention-1" not in titles


def test_list_archived_scope(client, staff):
    keep = NotificationFactory(recipient=staff, title="ActiveOne")
    archived = NotificationFactory(recipient=staff, title="ArchivedOne")
    archived.archive()
    client.force_login(staff)
    r = client.get(reverse("notifications:list") + "?scope=archived")
    titles = list(r.context["notifications"].values_list("title", flat=True))
    assert "ArchivedOne" in titles
    assert "ActiveOne" not in titles


def test_list_default_scope_excludes_archived(client, staff):
    archived = NotificationFactory(recipient=staff, title="Hidden")
    archived.archive()
    NotificationFactory(recipient=staff, title="Visible")
    client.force_login(staff)
    r = client.get(reverse("notifications:list"))
    titles = list(r.context["notifications"].values_list("title", flat=True))
    assert "Visible" in titles
    assert "Hidden" not in titles


def test_list_groups_have_today_bucket(client, staff):
    NotificationFactory(recipient=staff, title="Recent")
    client.force_login(staff)
    r = client.get(reverse("notifications:list"))
    assert b"Today" in r.content


def test_list_passes_counts_per_category(client, staff):
    NotificationFactory(recipient=staff, category="billing")
    NotificationFactory(recipient=staff, category="billing")
    NotificationFactory(recipient=staff, category="mention")
    client.force_login(staff)
    r = client.get(reverse("notifications:list"))
    counts = r.context["counts_by_category"]
    assert counts["billing"] == 2
    assert counts["mention"] == 1


# ── Archive view ─────────────────────────────────────────────────────


def test_archive_view_archives_notification(client, staff):
    n = NotificationFactory(recipient=staff)
    client.force_login(staff)
    r = client.post(reverse("notifications:archive", args=[n.pk]))
    assert r.status_code in (301, 302)
    n.refresh_from_db()
    assert n.archived_at is not None


def test_archive_view_restore_removes_archived_at(client, staff):
    n = NotificationFactory(recipient=staff)
    n.archive()
    client.force_login(staff)
    client.post(reverse("notifications:archive", args=[n.pk]),
                data={"action": "restore"})
    n.refresh_from_db()
    assert n.archived_at is None


def test_archive_view_only_owner(client):
    me = UserFactory()
    other = UserFactory()
    n = NotificationFactory(recipient=other)
    client.force_login(me)
    r = client.post(reverse("notifications:archive", args=[n.pk]))
    assert r.status_code == 404


# ── Preferences view ─────────────────────────────────────────────────


def test_preferences_get_renders_for_user(client, staff):
    client.force_login(staff)
    r = client.get(reverse("notifications:preferences"))
    assert r.status_code == 200
    body = r.content.decode()
    # Each category appears in the grid.
    for label in ("System", "Billing", "Mention", "Comment", "Security"):
        assert label in body


def test_preferences_post_persists_settings(client, staff):
    client.force_login(staff)
    client.post(reverse("notifications:preferences"), data={
        "billing__in_app": "on",
        "billing__email": "on",
        # billing__push omitted → off
        # everything else omitted → off
    })
    pref = NotificationPreference.objects.get(user=staff, category="billing")
    assert pref.in_app is True
    assert pref.email is True
    assert pref.push is False


def test_preferences_post_creates_row_per_category(client, staff):
    client.force_login(staff)
    client.post(reverse("notifications:preferences"), data={})
    # All five categories get a row, all defaults False.
    assert NotificationPreference.objects.filter(user=staff).count() == 5


def test_preferences_redirects_to_self(client, staff):
    client.force_login(staff)
    r = client.post(reverse("notifications:preferences"), data={})
    assert r.status_code == 302
    assert reverse("notifications:preferences") in r["Location"]


# ── Push subscription endpoints ──────────────────────────────────────


PUSH_PAYLOAD = {
    "endpoint": "https://push.example.com/abc",
    "keys": {"p256dh": "xxx-p256-yyy", "auth": "yyy-auth-xxx"},
}


def test_push_subscribe_creates_record(client, staff):
    client.force_login(staff)
    r = client.post(reverse("notifications:push_subscribe"),
                    data=json.dumps(PUSH_PAYLOAD),
                    content_type="application/json")
    assert r.status_code == 200
    body = json.loads(r.content)
    assert body["ok"] is True
    sub = PushSubscription.objects.get(user=staff)
    assert sub.endpoint == PUSH_PAYLOAD["endpoint"]


def test_push_subscribe_idempotent_on_same_endpoint(client, staff):
    client.force_login(staff)
    for _ in range(3):
        client.post(reverse("notifications:push_subscribe"),
                    data=json.dumps(PUSH_PAYLOAD),
                    content_type="application/json")
    assert PushSubscription.objects.count() == 1


def test_push_subscribe_rejects_missing_endpoint(client, staff):
    client.force_login(staff)
    r = client.post(reverse("notifications:push_subscribe"),
                    data=json.dumps({"keys": PUSH_PAYLOAD["keys"]}),
                    content_type="application/json")
    assert r.status_code == 400


def test_push_subscribe_rejects_invalid_json(client, staff):
    client.force_login(staff)
    r = client.post(reverse("notifications:push_subscribe"),
                    data="not-json",
                    content_type="application/json")
    assert r.status_code == 400


def test_push_unsubscribe_deletes_record(client, staff):
    client.force_login(staff)
    PushSubscription.objects.create(
        user=staff, endpoint=PUSH_PAYLOAD["endpoint"],
        p256dh="x", auth="y",
    )
    r = client.post(reverse("notifications:push_unsubscribe"),
                    data=json.dumps({"endpoint": PUSH_PAYLOAD["endpoint"]}),
                    content_type="application/json")
    assert r.status_code == 200
    assert PushSubscription.objects.count() == 0


def test_push_endpoints_require_auth(client):
    r = client.post(reverse("notifications:push_subscribe"),
                    data="{}", content_type="application/json")
    assert r.status_code in (301, 302)
