import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.views.generic import View

from apps.organizations.mixins import (
    HasRoleMixin,
    OrgRequiredMixin,
    OrgScopedMixin,
)


class _RoleView(HasRoleMixin, View):
    required_role = "admin"

    def get(self, request, *args, **kwargs):
        return "ok"


class _OrgRequiredView(OrgRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return "ok"


def _req(role=None, org=True):
    rf = RequestFactory()
    r = rf.get("/")
    r.organization = object() if org else None
    r.organization_role = role
    return r


def test_has_role_mixin_blocks_member_from_admin_route():
    with pytest.raises(PermissionDenied):
        _RoleView.as_view()(_req(role="member"))


def test_has_role_mixin_allows_owner_for_admin_route():
    assert _RoleView.as_view()(_req(role="owner")) == "ok"


def test_has_role_mixin_blocks_when_no_membership():
    with pytest.raises(PermissionDenied):
        _RoleView.as_view()(_req(role=None))


def test_org_required_mixin_redirects_when_no_org():
    response = _OrgRequiredView.as_view()(_req(org=False))
    assert response.status_code == 302
    assert "/orgs/" in response.url


def test_org_required_mixin_passes_through_when_org_present():
    assert _OrgRequiredView.as_view()(_req(org=True, role="member")) == "ok"


@pytest.mark.django_db
def test_org_scoped_mixin_filters_to_active_organization():
    from apps.accounts.tests.factories import UserFactory
    from apps.organizations.tests.factories import (
        MembershipFactory,
        OrganizationFactory,
    )

    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    user = UserFactory()
    m_a = MembershipFactory(user=user, organization=org_a)
    MembershipFactory(user=user, organization=org_b)

    class Stub(OrgScopedMixin):
        request = type("R", (), {"organization": org_a})()

        def get_queryset(self):  # super().get_queryset() target
            from apps.organizations.models import Membership
            return Membership.objects.all()

    # Inject parent get_queryset by walking the MRO manually via super-calls.
    class _Q:
        def get_queryset(self):
            from apps.organizations.models import Membership
            return Membership.objects.all()

    class V(OrgScopedMixin, _Q):
        request = type("R", (), {"organization": org_a})()

    qs = V().get_queryset()
    assert list(qs) == [m_a]


@pytest.mark.django_db
def test_org_scoped_mixin_returns_none_when_no_active_org():
    class _Q:
        def get_queryset(self):
            from apps.organizations.models import Membership
            return Membership.objects.all()

    class V(OrgScopedMixin, _Q):
        request = type("R", (), {"organization": None})()

    assert list(V().get_queryset()) == []
