import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.organizations.middleware import SESSION_KEY
from apps.organizations.models import Invitation, Membership, Organization
from apps.organizations.tests.factories import (
    InvitationFactory,
    MembershipFactory,
    OrganizationFactory,
)


@pytest.fixture
def verified_user(db):
    from django.utils import timezone
    user = UserFactory()
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


@pytest.fixture
def auth_client(client, verified_user):
    client.force_login(verified_user)
    return client


# ── List + create ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_org_list_renders_for_authed_user(auth_client, verified_user):
    org = OrganizationFactory(name="Apex Demo")
    MembershipFactory(user=verified_user, organization=org)
    r = auth_client.get(reverse("organizations:list"))
    assert r.status_code == 200
    assert b"Apex Demo" in r.content


@pytest.mark.django_db
def test_org_list_post_creates_org_with_user_as_owner(auth_client, verified_user):
    r = auth_client.post(reverse("organizations:list"), {"name": "New Co"})
    org = Organization.objects.get(name="New Co")
    assert r.status_code == 302
    assert r.url == reverse("organizations:settings", kwargs={"slug": org.slug})
    membership = Membership.objects.get(user=verified_user, organization=org)
    assert membership.role == "owner"


@pytest.mark.django_db
def test_org_list_rejects_blank_name(auth_client):
    r = auth_client.post(reverse("organizations:list"), {"name": "   "})
    assert r.status_code == 302
    assert Organization.objects.count() == 0


# ── Switcher ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_org_switch_sets_session_for_member(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org)
    r = auth_client.post(reverse("organizations:switch",
                                 kwargs={"slug": org.slug}))
    assert r.status_code == 302
    assert auth_client.session[SESSION_KEY] == org.slug


@pytest.mark.django_db
def test_org_switch_rejects_non_member(auth_client):
    other = OrganizationFactory()
    r = auth_client.post(reverse("organizations:switch",
                                 kwargs={"slug": other.slug}))
    assert r.status_code == 302
    assert SESSION_KEY not in auth_client.session


# ── Settings ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_settings_requires_admin_role(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="member")
    r = auth_client.get(reverse("organizations:settings",
                                kwargs={"slug": org.slug}))
    assert r.status_code == 403


@pytest.mark.django_db
def test_settings_renders_for_admin(auth_client, verified_user):
    org = OrganizationFactory(name="Acme HQ")
    MembershipFactory(user=verified_user, organization=org, role="admin")
    r = auth_client.get(reverse("organizations:settings",
                                kwargs={"slug": org.slug}))
    assert r.status_code == 200
    assert b"Acme HQ" in r.content


@pytest.mark.django_db
def test_settings_post_updates_name_and_plan(auth_client, verified_user):
    org = OrganizationFactory(name="Old Name", plan="free")
    MembershipFactory(user=verified_user, organization=org, role="owner")
    auth_client.post(
        reverse("organizations:settings", kwargs={"slug": org.slug}),
        {"name": "New Name", "plan": "pro"},
    )
    org.refresh_from_db()
    assert org.name == "New Name"
    assert org.plan == "pro"


@pytest.mark.django_db
def test_settings_delete_only_for_owner(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    auth_client.post(
        reverse("organizations:settings", kwargs={"slug": org.slug}),
        {"action": "delete"},
    )
    assert Organization.objects.filter(pk=org.pk).exists()


@pytest.mark.django_db
def test_settings_delete_works_for_owner(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="owner")
    auth_client.post(
        reverse("organizations:settings", kwargs={"slug": org.slug}),
        {"action": "delete"},
    )
    assert not Organization.objects.filter(pk=org.pk).exists()


# ── Members + invitations ─────────────────────────────────────────────


@pytest.mark.django_db
def test_members_view_lists_members_and_pending(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="owner")
    other = UserFactory(username="teammate")
    MembershipFactory(user=other, organization=org, role="member")
    InvitationFactory(organization=org, email="pending@example.com")
    r = auth_client.get(reverse("organizations:members",
                                kwargs={"slug": org.slug}))
    assert r.status_code == 200
    assert b"teammate" in r.content
    assert b"pending@example.com" in r.content


@pytest.mark.django_db
def test_invite_view_creates_invitation(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    auth_client.post(
        reverse("organizations:invite", kwargs={"slug": org.slug}),
        {"email": "new@example.com", "role": "member"},
    )
    assert Invitation.objects.filter(
        organization=org, email="new@example.com",
    ).exists()


@pytest.mark.django_db
def test_invite_view_rejects_duplicate(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    InvitationFactory(organization=org, email="dup@example.com")
    auth_client.post(
        reverse("organizations:invite", kwargs={"slug": org.slug}),
        {"email": "dup@example.com", "role": "member"},
    )
    assert org.invitations.filter(email="dup@example.com").count() == 1


@pytest.mark.django_db
def test_change_role_updates_membership(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    target = MembershipFactory(organization=org, role="member")
    auth_client.post(
        reverse("organizations:change_role",
                kwargs={"slug": org.slug, "pk": target.pk}),
        {"role": "billing"},
    )
    target.refresh_from_db()
    assert target.role == "billing"


@pytest.mark.django_db
def test_remove_member_deletes_membership(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    target = MembershipFactory(organization=org, role="member")
    auth_client.post(
        reverse("organizations:remove_member",
                kwargs={"slug": org.slug, "pk": target.pk}),
    )
    assert not Membership.objects.filter(pk=target.pk).exists()


@pytest.mark.django_db
def test_remove_member_refuses_to_remove_owner(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="owner")
    other_owner = MembershipFactory(organization=org, role="owner")
    auth_client.post(
        reverse("organizations:remove_member",
                kwargs={"slug": org.slug, "pk": other_owner.pk}),
    )
    assert Membership.objects.filter(pk=other_owner.pk).exists()


@pytest.mark.django_db
def test_cancel_invitation_deletes_it(auth_client, verified_user):
    org = OrganizationFactory()
    MembershipFactory(user=verified_user, organization=org, role="admin")
    inv = InvitationFactory(organization=org)
    auth_client.post(
        reverse("organizations:cancel_invitation",
                kwargs={"slug": org.slug, "pk": inv.pk}),
    )
    assert not Invitation.objects.filter(pk=inv.pk).exists()


# ── Public accept ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_accept_view_get_renders(client):
    inv = InvitationFactory()
    r = client.get(reverse("invitation_accept", kwargs={"token": inv.token}))
    assert r.status_code == 200
    assert inv.organization.name.encode() in r.content


@pytest.mark.django_db
def test_accept_view_get_invalid_token(client):
    r = client.get(reverse("invitation_accept", kwargs={"token": "nope"}))
    assert r.status_code == 200
    assert b"not found" in r.content.lower()


@pytest.mark.django_db
def test_accept_view_post_anonymous_redirects_to_login(client):
    inv = InvitationFactory()
    r = client.post(reverse("invitation_accept", kwargs={"token": inv.token}))
    assert r.status_code == 302
    assert "/accounts/login/" in r.url


@pytest.mark.django_db
def test_accept_view_post_creates_membership_and_switches(auth_client,
                                                          verified_user):
    inv = InvitationFactory(email=verified_user.email)
    r = auth_client.post(
        reverse("invitation_accept", kwargs={"token": inv.token}),
    )
    assert r.status_code == 302
    assert Membership.objects.filter(
        user=verified_user, organization=inv.organization,
    ).exists()
    assert auth_client.session[SESSION_KEY] == inv.organization.slug


@pytest.mark.django_db
def test_accept_view_post_rejects_email_mismatch(auth_client, verified_user):
    inv = InvitationFactory(email="someoneelse@example.com")
    auth_client.post(
        reverse("invitation_accept", kwargs={"token": inv.token}),
    )
    assert not Membership.objects.filter(
        user=verified_user, organization=inv.organization,
    ).exists()


@pytest.mark.django_db
def test_accept_view_post_rejects_expired(auth_client, verified_user):
    from datetime import timedelta

    from django.utils import timezone

    inv = InvitationFactory(
        email=verified_user.email,
        expires_at=timezone.now() - timedelta(days=1),
    )
    auth_client.post(
        reverse("invitation_accept", kwargs={"token": inv.token}),
    )
    assert not Membership.objects.filter(
        user=verified_user, organization=inv.organization,
    ).exists()
