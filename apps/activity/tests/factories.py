import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.activity.models import ActivityEvent


class ActivityEventFactory(DjangoModelFactory):
    class Meta:
        model = ActivityEvent

    actor = factory.SubFactory(UserFactory)
    category = "system"
    verb = "did"
    label = factory.Sequence(lambda n: f"Thing {n}")
