import factory

from apps.accounts.tests.factories import UserFactory
from apps.chat.models import ChatMessage


class ChatMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ChatMessage

    sender = factory.SubFactory(UserFactory)
    recipient = factory.SubFactory(UserFactory)
    body = factory.Faker("sentence", nb_words=10)
    is_read = False
