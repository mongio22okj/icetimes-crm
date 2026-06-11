import factory

from apps.accounts.tests.factories import UserFactory
from apps.kanban.models import Card


class CardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Card

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph", nb_sentences=2)
    status = "todo"
    priority = "med"
    position = 0
    created_by = factory.SubFactory(UserFactory)
