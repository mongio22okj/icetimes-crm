from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.organizations.models import (
    Invitation,
    Membership,
    Organization,
    role_at_least,
)
from apps.organizations.tests.factories import (
    InvitationFactory,
    MembershipFactory,
    OrganizationFactory,
)


@pytest.mark.django_db
def test_organization_auto_slugifies_name():
    org = Organization.objects.create(name="Acme Corp")
    assert org.slug == "acme-corp"


@pytest.mark.django_db
def test_organization_slug_collisions_get_a_suffix():
    Organization.objects.create(name="Acme")
    other = Organization.objects.create(name="Acme")
    assert other.slug == "acme-2"


@pytest.mark.django_db
def test_organization_initials_handles_one_and_two_word_names():
    one = OrganizationFactory(name="Apex")
    two = OrganizationFactory(name="Apex Co")
    assert one.initials() == "AP"
    assert two.initials() == "AC"


@pytest.mark.django_db
def test_organization_get_absolute_url_points_at_settings():
    org = OrganizationFactory(name="Acme Holdings")
    assert org.get_absolute_url().endswith(f"/orgs/{org.slug}/settings/")


@pytest.mark.django_db
def test_membership_unique_per_user_per_org():
    user = UserFactory()
    org = OrganizationFactory()
    MembershipFactory(user=user, organization=org)
    with pytest.raises(Exception):
        Membership.objects.create(user=user, organization=org, role="admin")


def test_role_at_least_strict_ordering():
    assert role_at_least("owner", "admin") is True
    assert role_at_least("admin", "admin") is True
    assert role_at_least("member", "admin") is False
    assert role_at_least("viewer", "owner") is False
    # Unknown roles return False (defensive).
    assert role_at_least("nope", "admin") is False
    assert role_at_least("admin", "nope") is False


@pytest.mark.django_db
def test_invitation_create_for_normalizes_email_and_sets_expiry():
    org = OrganizationFactory()
    user = UserFactory()
    inv = Invitation.create_for(org, email="  Foo@BAR.com ", role="admin",
                                invited_by=user)
    assert inv.email == "foo@bar.com"
    assert inv.token  # populated
    assert inv.expires_at > timezone.now()


@pytest.mark.django_db
def test_invitation_is_expired_and_is_pending():
    fresh = InvitationFactory()
    assert fresh.is_pending is True
    assert fresh.is_expired is False
    expired = InvitationFactory(expires_at=timezone.now() - timedelta(days=1))
    assert expired.is_expired is True
    assert expired.is_pending is False


@pytest.mark.django_db
def test_invitation_accept_creates_membership_and_is_idempotent():
    org = OrganizationFactory()
    user = UserFactory(email="x@y.com")
    inv = InvitationFactory(organization=org, email="x@y.com", role="admin")
    m1 = inv.accept(user)
    assert m1.role == "admin"
    assert inv.accepted_at is not None
    # Second accept call doesn't blow up or duplicate.
    m2 = inv.accept(user)
    assert m1.pk == m2.pk
    assert Membership.objects.filter(user=user, organization=org).count() == 1


@pytest.mark.django_db
def test_invitation_get_absolute_url_uses_top_level_pattern():
    inv = InvitationFactory()
    url = inv.get_absolute_url()
    assert url == f"/invitations/{inv.token}/"
