import factory

from apps.accounts.tests.factories import UserFactory
from apps.organizations.models import Invitation, Membership, Organization


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Org {n}")
    plan = "free"
    created_by = factory.SubFactory(UserFactory)


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = "member"


class InvitationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invitation

    organization = factory.SubFactory(OrganizationFactory)
    email = factory.Sequence(lambda n: f"invite{n}@example.com")
    role = "member"
    token = factory.Sequence(lambda n: f"token-{n}-abcdef")
    expires_at = factory.LazyFunction(
        lambda: __import__("django.utils.timezone", fromlist=["now"]).now()
                + __import__("datetime").timedelta(days=14),
    )
