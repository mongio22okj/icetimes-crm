import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.accounts.tests.factories import UserFactory
from apps.organizations.middleware import (
    SESSION_KEY,
    OrganizationMiddleware,
    set_active_organization,
)
from apps.organizations.tests.factories import (
    MembershipFactory,
    OrganizationFactory,
)


def _make_request(user=None):
    rf = RequestFactory()
    req = rf.get("/")
    req.user = user or AnonymousUser()
    req.session = {}
    return req


def _run_middleware(request):
    called = {}

    def get_response(req):
        called["yes"] = True
        return "ok"

    OrganizationMiddleware(get_response)(request)
    assert called["yes"]
    return request


@pytest.mark.django_db
def test_anonymous_request_gets_none_org():
    req = _run_middleware(_make_request())
    assert req.organization is None
    assert req.memberships == []


@pytest.mark.django_db
def test_authenticated_no_membership_gets_none_org():
    user = UserFactory()
    req = _run_middleware(_make_request(user=user))
    assert req.organization is None
    assert req.memberships == []


@pytest.mark.django_db
def test_authenticated_picks_first_membership_alphabetically():
    user = UserFactory()
    z = OrganizationFactory(name="Zeta")
    a = OrganizationFactory(name="Alpha")
    MembershipFactory(user=user, organization=z, role="admin")
    MembershipFactory(user=user, organization=a, role="member")
    req = _run_middleware(_make_request(user=user))
    assert req.organization == a
    assert req.organization_role == "member"
    # Session is now sticky on the chosen slug.
    assert req.session[SESSION_KEY] == a.slug


@pytest.mark.django_db
def test_session_slug_overrides_default():
    user = UserFactory()
    a = OrganizationFactory(name="Alpha")
    z = OrganizationFactory(name="Zeta")
    MembershipFactory(user=user, organization=a)
    MembershipFactory(user=user, organization=z, role="admin")
    req = _make_request(user=user)
    req.session[SESSION_KEY] = z.slug
    _run_middleware(req)
    assert req.organization == z
    assert req.organization_role == "admin"


@pytest.mark.django_db
def test_set_active_organization_rejects_non_member():
    user = UserFactory()
    other = OrganizationFactory()
    req = _make_request(user=user)
    set_active_organization(req, other)
    assert SESSION_KEY not in req.session


@pytest.mark.django_db
def test_set_active_organization_persists_for_member():
    user = UserFactory()
    org = OrganizationFactory()
    MembershipFactory(user=user, organization=org)
    req = _make_request(user=user)
    set_active_organization(req, org)
    assert req.session[SESSION_KEY] == org.slug
    assert req.organization == org
