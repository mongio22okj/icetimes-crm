from datetime import timedelta

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    owner = factory.SubFactory(UserFactory)
    title = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("paragraph", nb_sentences=2)
    start = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    end = factory.LazyAttribute(lambda o: o.start + timedelta(hours=1))
    all_day = False
    category = "meeting"
